"""
Testes de integração CLI para o controlador_semaforo.py.
"""

import sys
from unittest.mock import patch
import pytest
from controlador_semaforo import parse_args


def test_parse_args_defaults():
    with patch.object(sys, "argv", ["controlador_semaforo.py"]):
        args = parse_args()
        assert args.camera == 0
        assert args.video is None
        assert args.serial == "none"
        assert args.baud == 9600
        assert args.t_min_verde == 5.0
        assert args.t_max_verde == 25.0
        assert args.t_pedestre == 8.0
        assert args.conf == 0.30
        assert args.imgsz == 416


def test_parse_args_custom():
    custom_args = [
        "controlador_semaforo.py",
        "--video", "maquete_teste.mp4",
        "--serial", "/dev/ttyUSB0",
        "--baud", "115200",
        "--t-min-verde", "7.0",
        "--t-max-verde", "30.0",
        "--conf", "0.45",
    ]
    with patch.object(sys, "argv", custom_args):
        args = parse_args()
        assert str(args.video) == "maquete_teste.mp4"
        assert args.serial == "/dev/ttyUSB0"
        assert args.baud == 115200
        assert args.t_min_verde == 7.0
        assert args.t_max_verde == 30.0
        assert args.conf == 0.45
