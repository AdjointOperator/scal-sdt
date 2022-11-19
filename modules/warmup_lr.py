# Copy pasted from https://github.com/lehduong/torch-warmup-lr/blob/master/torch_warmup_lr/wrappers.py with modifications

import math
from typing import Literal

from torch.optim.lr_scheduler import _LRScheduler


class WarmupLR(_LRScheduler):
    _warmup_last_epoch = 0

    def __init__(self, scheduler, init_lr=1e-3,
                 num_warmup=1, warmup_strategy: Literal['linear', 'cosine', 'constant'] = 'constant'):
        self._scheduler = scheduler
        self._init_lr = init_lr
        self._num_warmup = num_warmup
        self._step_count = 0
        # Define the strategy to warm up learning rate
        self._warmup_strategy = warmup_strategy
        if warmup_strategy == 'cosine':
            self._warmup_func = self._warmup_cos
        elif warmup_strategy == 'linear':
            self._warmup_func = self._warmup_linear
        elif warmup_strategy == 'cosine':
            self._warmup_func = self._warmup_const
        else:
            raise ValueError(
                f"Expect warmup_strategy to be one of ['linear', 'cosine', 'constant'] but got {warmup_strategy}")
        # save initial learning rate of each param group
        # only useful when each param groups having different learning rate
        self._format_param()

    def __getattr__(self, name):
        return getattr(self._scheduler, name)

    def state_dict(self):
        """Returns the state of the scheduler as a :class:`dict`.
        It contains an entry for every variable in self.__dict__ which
        is not the optimizer.
        """
        wrapper_state_dict = {key: value for key, value in self.__dict__.items() if
                              (key != 'optimizer' and key != '_scheduler')}
        wrapped_state_dict = {key: value for key, value in self._scheduler.__dict__.items() if key != 'optimizer'}
        return {'scheduler': wrapped_state_dict, 'warmup': wrapper_state_dict}

    def load_state_dict(self, state_dict):
        """Loads the schedulers state.
        Arguments:
            state_dict (dict): scheduler state. Should be an object returned
                from a call to :meth:`state_dict`.
        """
        self.__dict__.update(state_dict['warmup'])
        self._scheduler.__dict__.update(state_dict['scheduler'])

    def _format_param(self):
        # learning rate of each param group will increase
        # from the min_lr to initial_lr
        for group in self._scheduler.optimizer.param_groups:
            group['warmup_max_lr'] = group['lr']
            group['warmup_initial_lr'] = min(self._init_lr, group['lr'])

    @staticmethod
    def _warmup_cos(start, end, pct):
        cos_out = math.cos(math.pi * pct) + 1
        return end + (start - end) / 2.0 * cos_out

    @staticmethod
    def _warmup_const(start, end, pct):
        return start if pct < 0.9999 else end

    @staticmethod
    def _warmup_linear(start, end, pct):
        return (end - start) * pct + start

    def get_lr(self):
        lrs = []
        step_num = self._step_count
        # warm up learning rate
        if step_num <= self._num_warmup:
            for group in self._scheduler.optimizer.param_groups:
                computed_lr = self._warmup_func(group['warmup_initial_lr'],
                                                group['warmup_max_lr'],
                                                step_num / self._num_warmup)
                lrs.append(computed_lr)
        else:
            lrs = self._scheduler.get_lr()
        return lrs

    def step(self, epoch):
        if self._step_count <= self._num_warmup:
            values = self.get_lr()
            for param_group, lr in zip(self._scheduler.optimizer.param_groups, values):
                param_group['lr'] = lr
            self._step_count += 1
            self._warmup_last_epoch = epoch
        else:
            self._scheduler.step(epoch - self._warmup_last_epoch)
