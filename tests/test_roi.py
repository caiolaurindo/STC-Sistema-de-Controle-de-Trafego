"""
Testes unitários para o módulo de Regiões de Interesse (ROIs).
"""

import tempfile
from pathlib import Path
from stc.roi import ROI, ROIManager, ponto_no_poligono


def test_ponto_no_poligono():
    # Quadrado de (0,0) até (10,10)
    quadrado = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]

    # Pontos dentro
    assert ponto_no_poligono(5.0, 5.0, quadrado) is True
    assert ponto_no_poligono(1.0, 1.0, quadrado) is True
    assert ponto_no_poligono(9.0, 9.0, quadrado) is True

    # Pontos fora
    assert ponto_no_poligono(-1.0, 5.0, quadrado) is False
    assert ponto_no_poligono(5.0, 11.0, quadrado) is False
    assert ponto_no_poligono(15.0, 15.0, quadrado) is False


def test_roi_pixel_coords_and_containment():
    roi = ROI("Zona Teste", [(0.1, 0.2), (0.5, 0.2), (0.5, 0.8), (0.1, 0.8)])

    # Resolução 1000x500
    pixels = roi.to_pixel_coords(largura=1000, altura=500)
    assert pixels == [(100, 100), (500, 100), (500, 400), (100, 400)]

    # Ponto no centro (300, 250) deve estar dentro
    assert roi.contem_ponto(300, 250, largura=1000, altura=500) is True

    # Ponto fora (50, 50) deve estar fora
    assert roi.contem_ponto(50, 50, largura=1000, altura=500) is False


def test_roimanager_json_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "teste_rois.json"
        mgr = ROIManager(arquivo_json=str(json_path))

        assert json_path.exists()
        assert "via_a" in mgr.rois
        assert "via_b" in mgr.rois
        assert "pedestre" in mgr.rois

        # Altera uma coordenada e salva
        mgr.rois["via_a"].pontos = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]
        mgr.salvar()

        # Recarrega em nova instância
        mgr2 = ROIManager(arquivo_json=str(json_path))
        assert mgr2.rois["via_a"].pontos[0] == (0.2, 0.2)


def test_roimanager_processar_deteccoes():
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "teste_rois.json"
        mgr = ROIManager(arquivo_json=str(json_path))

        # Modifica as ROIs para posições fáceis de testar em frame 1000x1000
        # Via A: x [300, 700], y [600, 900]
        mgr.rois["via_a"] = ROI("Via A", [(0.3, 0.6), (0.7, 0.6), (0.7, 0.9), (0.3, 0.9)])
        # Via B: x [0, 300], y [300, 600]
        mgr.rois["via_b"] = ROI("Via B", [(0.0, 0.3), (0.3, 0.3), (0.3, 0.6), (0.0, 0.6)])
        # Pedestre: x [300, 700], y [400, 550]
        mgr.rois["pedestre"] = ROI("Pedestre", [(0.3, 0.4), (0.7, 0.4), (0.7, 0.55), (0.3, 0.55)])

        deteccoes = [
            # Carro na Via A: contato chão (500, 750) -> dentro
            {"bbox": (450, 700, 550, 750), "cls_name": "carro_de_brinquedo", "conf": 0.9},
            # Outro carro na Via A: contato chão (400, 850) -> dentro
            {"bbox": (350, 800, 450, 850), "cls_name": "carro_de_brinquedo", "conf": 0.85},
            # Carro na Via B: contato chão (150, 450) -> dentro
            {"bbox": (100, 400, 200, 450), "cls_name": "carro_de_brinquedo", "conf": 0.88},
            # Pedestre na Faixa: contato chão (500, 500) -> dentro
            {"bbox": (480, 460, 520, 500), "cls_name": "boneco_de_brinquedo", "conf": 0.92},
            # Carro fora das ROIs: contato chão (900, 900) -> fora
            {"bbox": (850, 850, 950, 900), "cls_name": "carro_de_brinquedo", "conf": 0.7},
        ]

        resultado = mgr.processar_deteccoes(deteccoes, largura_frame=1000, altura_frame=1000)

        assert resultado["carros_via_a"] == 2
        assert resultado["carros_via_b"] == 1
        assert resultado["pedestre_detectado"] is True
        assert resultado["pedestres_contagem"] == 1
