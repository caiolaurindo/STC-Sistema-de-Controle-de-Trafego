"""
Pacote STC - Sistema de Controle de Tráfego Adaptativo
Integração de Visão Computacional (YOLOv8), Máquina de Estados e Controle Físico.
"""

from stc.controller import State, TrafficController, TrafficSignal
from stc.roi import ROI, ROIManager
from stc.serial_comm import TrafficSerialCommunicator
from stc.detector import YOLODetector
from stc.visualizer import TrafficVisualizer, ROICalibrator

__all__ = [
    "TrafficController",
    "State",
    "TrafficSignal",
    "ROIManager",
    "ROI",
    "TrafficSerialCommunicator",
    "YOLODetector",
    "TrafficVisualizer",
    "ROICalibrator",
]
