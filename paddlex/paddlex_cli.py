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
import argparse
import subprocess
import sys
import shutil
import tempfile
from pathlib import Path

from . import create_pipeline
from .inference.pipelines import create_pipeline_from_config, load_pipeline_config
from .repo_manager import setup, get_all_supported_repo_names
from .utils.cache import CACHE_DIR
from .utils import logging
from .utils.interactive_get_pipeline import interactive_get_pipeline


def _install_serving_deps():
    SERVING_DEPS = [
        "aiohttp>=3.9",
        "bce-python-sdk>=0.8",
        "fastapi>=0.110",
        "pydantic>=2",
        "starlette>=0.36",
        "typing_extensions>=4.11",
        "uvicorn>=0.16",
        "yarl>=1.9",
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8") as f:
        for dep in SERVING_DEPS:
            f.write(dep + "\n")
        f.flush()
        return subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", f.name]
        )


def args_cfg():
    """parse cli arguments"""

    def parse_str(s):
        """convert str type value
        to None type if it is "None",
        to bool type if it means True or False.
        """
        if s in ("None"):
            return None
        elif s in ("TRUE", "True", "true", "T", "t"):
            return True
        elif s in ("FALSE", "False", "false", "F", "f"):
            return False
        return s

    parser = argparse.ArgumentParser()

    ################# install pdx #################
    parser.add_argument("--install", action="store_true", default=False, help="")
    parser.add_argument("--clear_cache", action="store_true", default=False, help="")
    parser.add_argument("plugins", nargs="*", default=[])
    parser.add_argument("--no_deps", action="store_true")
    parser.add_argument("--platform", type=str, default="github.com")
    parser.add_argument(
        "-y",
        "--yes",
        dest="update_repos",
        action="store_true",
        help="Whether to update_repos all packages.",
    )
    parser.add_argument(
        "--use_local_repos",
        action="store_true",
        default=False,
        help="Use local repos when existing.",
    )

    ################# pipeline predict #################
    parser.add_argument("--pipeline", type=str, help="")
    parser.add_argument("--input", type=str, default=None, help="")
    parser.add_argument("--save_path", type=str, default=None, help="")
    parser.add_argument("--device", type=str, default=None, help="")
    parser.add_argument("--use_hpip", action="store_true")
    parser.add_argument("--serial_number", type=str)
    parser.add_argument("--update_license", action="store_true")
    parser.add_argument("--get_pipeline_config", type=str, default=None, help="")

    ################# serving #################
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)

    return parser


def install(args):
    """install paddlex"""
    # Enable debug info
    os.environ["PADDLE_PDX_DEBUG"] = "True"
    # Disable eager initialization
    os.environ["PADDLE_PDX_EAGER_INIT"] = "False"

    plugins = args.plugins[:]

    if "serving" in plugins:
        plugins.remove("serving")
        _install_serving_deps()
        return

    if plugins:
        repo_names = plugins
    elif len(plugins) == 0:
        repo_names = get_all_supported_repo_names()
    setup(
        repo_names=repo_names,
        no_deps=args.no_deps,
        platform=args.platform,
        update_repos=args.update_repos,
        use_local_repos=args.use_local_repos,
    )
    return


def _get_hpi_params(serial_number, update_license):
    return {"serial_number": serial_number, "update_license": update_license}


def pipeline_predict(
    pipeline, input, device, save_path, use_hpip, serial_number, update_license
):
    """pipeline predict"""
    hpi_params = _get_hpi_params(serial_number, update_license)
    pipeline = create_pipeline(
        pipeline, device=device, use_hpip=use_hpip, hpi_params=hpi_params
    )
    result = pipeline(input)
    for res in result:
        res.print(json_format=False)
        if save_path:
            res.save_all(save_path=save_path)


def serve(pipeline, *, device, use_hpip, serial_number, update_license, host, port):
    from .inference.pipelines.serving import create_pipeline_app, run_server

    hpi_params = _get_hpi_params(serial_number, update_license)
    pipeline_config = load_pipeline_config(pipeline)
    pipeline = create_pipeline_from_config(
        pipeline_config, device=device, use_hpip=use_hpip, hpi_params=hpi_params
    )
    app = create_pipeline_app(pipeline, pipeline_config)
    run_server(app, host=host, port=port, debug=False)


def clear_cache():
    cache_dir = Path(CACHE_DIR) / "official_models"
    if cache_dir.exists() and cache_dir.is_dir():
        shutil.rmtree(cache_dir)
        logging.info(f"Successfully cleared the cache models at {cache_dir}")
    else:
        logging.info(f"No cache models found at {cache_dir}")


# for CLI
def main():
    """API for commad line"""
    args = args_cfg().parse_args()
    if len(sys.argv) == 1:
        logging.warning("No arguments provided. Displaying help information:")
        args_cfg().print_help()
        return

    if args.install:
        install(args)
    elif args.serve:
        serve(
            args.pipeline,
            device=args.device,
            use_hpip=args.use_hpip,
            serial_number=args.serial_number,
            update_license=args.update_license,
            host=args.host,
            port=args.port,
        )
    elif args.clear_cache:
        clear_cache()
    else:
        if args.get_pipeline_config is not None:
            interactive_get_pipeline(args.get_pipeline_config, args.save_path)
        else:
            return pipeline_predict(
                args.pipeline,
                args.input,
                args.device,
                args.save_path,
                use_hpip=args.use_hpip,
                serial_number=args.serial_number,
                update_license=args.update_license,
            )
