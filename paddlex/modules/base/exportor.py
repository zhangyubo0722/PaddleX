# copyright (c) 2024 PaddlePaddle Authors. All Rights Reserve.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from pathlib import Path
from abc import ABC, abstractmethod

from .build_model import build_model
from ...utils.device import (
    update_device_num,
    set_env_for_device,
    parse_device,
    check_device,
)
from ...utils.misc import AutoRegisterABCMetaClass
from ...utils.config import AttrDict
from ...utils import logging


def build_exportor(config: AttrDict) -> "BaseExportor":
    """build model exportor

    Args:
        config (AttrDict): PaddleX pipeline config, which is loaded from pipeline yaml file.

    Returns:
        BaseExportor: the exportor, which is subclass of BaseExportor.
    """
    model_name = config.Global.model
    return BaseExportor.get(model_name)(config)


class BaseExportor(ABC, metaclass=AutoRegisterABCMetaClass):
    """Base Model Exportor"""

    __is_base = True

    def __init__(self, config):
        """Initialize the instance.

        Args:
            config (AttrDict):  PaddleX pipeline config, which is loaded from pipeline yaml file.
        """
        super().__init__()
        self.global_config = config.Global
        self.export_config = config.Export

        config_path = self.get_config_path(self.export_config.weight_path)

        self.pdx_config, self.pdx_model = build_model(
            self.global_config.model, config_path=config_path
        )

    def get_config_path(self, weight_path):
        """
        get config path

        Args:
            weight_path (str): The path to the weight

        Returns:
            config_path (str): The path to the config

        """

        config_path = Path(weight_path).parent / "config.yaml"
        if not config_path.exists():
            logging.warning(
                f"The config file(`{config_path}`) related to weight file(`{weight_path}`) is not exist, use default instead."
            )
            config_path = None

        return config_path

    def export(self) -> dict:
        """execute model exporting

        Returns:
            dict: the export metrics
        """
        self.update_config()
        export_result = self.pdx_model.export(**self.get_export_kwargs())
        assert (
            export_result.returncode == 0
        ), f"Encountered an unexpected error({export_result.returncode}) in \
exporting!"

        return None

    def get_device(self, using_device_number: int = None) -> str:
        """get device setting from config

        Args:
            using_device_number (int, optional): specify device number to use.
                Defaults to None, means that base on config setting.

        Returns:
            str: device setting, such as: `gpu:0,1`, `npu:0,1`, `cpu`.
        """
        device_type, device_ids = parse_device(self.global_config.device)
        check_device(self.global_config.model, device_type)
        if using_device_number:
            return update_device_num(device_type, device_ids, using_device_number)
        set_env_for_device(self.global_config.device)
        return self.global_config.device

    def update_config(self):
        """update export config"""
        pass

    def get_export_kwargs(self):
        """get key-value arguments of model export function"""
        return {
            "weight_path": self.export_config.weight_path,
            "save_dir": self.global_config.output,
            "device": self.get_device(),
        }
