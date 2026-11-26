"""
Módulo de Regiões de Interesse (ROIs) do STC.
Gerencia as áreas de detecção (Via A, Via B, Faixa de Pedestre),
testes de inclusão geométrica e persistência em arquivo JSON.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional


def ponto_no_poligono(x: float, y: float, poligono: List[Tuple[float, float]]) -> bool:
    """
    Algoritmo Ray-Casting para verificar se o ponto (x, y) está dentro do polígono.
    Independente de bibliotecas externas (executa em Python puro).
    """
    n = len(poligono)
    if n < 3:
        return False

    dentro = False
    p1x, p1y = poligono[0]
    for i in range(1, n + 1):
        p2x, p2y = poligono[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        dentro = not dentro
        p1x, p1y = p2x, p2y

    return dentro


class ROI:
    """
    Representa uma região de interesse com coordenadas normalizadas (0.0 a 1.0).
    """

    def __init__(self, nome: str, pontos: List[Tuple[float, float]]):
        self.nome = nome
        self.pontos = [tuple(p) for p in pontos]

    def to_pixel_coords(self, largura: int, altura: int) -> List[Tuple[int, int]]:
        """Converte pontos normalizados para coordenadas em pixels."""
        return [
            (int(px * largura), int(py * altura))
            for px, py in self.pontos
        ]

    def contem_ponto(self, px: float, py: float, largura: Optional[int] = None, altura: Optional[int] = None) -> bool:
        """
        Verifica se um ponto está dentro da ROI.
        Se largura e altura forem passadas, px e py são tratados como coordenadas em pixels.
        """
        if largura is not None and altura is not None:
            norm_x = px / max(1, largura)
            norm_y = py / max(1, altura)
        else:
            norm_x, norm_y = px, py

        return ponto_no_poligono(norm_x, norm_y, self.pontos)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nome": self.nome,
            "pontos": [[round(x, 4), round(y, 4)] for x, y in self.pontos],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ROI":
        return cls(nome=data["nome"], pontos=[(p[0], p[1]) for p in data["pontos"]])


class ROIManager:
    """
    Gerenciador das regiões de interesse do cruzamento viário.
    """

    def __init__(self, arquivo_json: Optional[str] = None):
        self.rois: Dict[str, ROI] = {}
        self.arquivo_json = Path(arquivo_json) if arquivo_json else Path("rois.json")

        if self.arquivo_json.exists():
            self.carregar()
        else:
            self._criar_rois_padrao()
            self.salvar()

    def _criar_rois_padrao(self) -> None:
        """Configuração inicial padrão proporcional ao cruzamento da maquete."""
        self.rois = {
            # Via A: Via vertical (fila de aproximação de baixo para o centro)
            "via_a": ROI("Via A (Norte-Sul)", [
                (0.35, 0.58),
                (0.65, 0.58),
                (0.65, 0.95),
                (0.35, 0.95),
            ]),
            # Via B: Via horizontal (aproximação lateral esquerda)
            "via_b": ROI("Via B (Leste-Oeste)", [
                (0.05, 0.35),
                (0.35, 0.35),
                (0.35, 0.65),
                (0.05, 0.65),
            ]),
            # Faixa de Pedestre: área sobre a faixa de travessia
            "pedestre": ROI("Faixa de Pedestre", [
                (0.35, 0.42),
                (0.65, 0.42),
                (0.65, 0.56),
                (0.35, 0.56),
            ]),
        }

    def salvar(self, caminho: Optional[str] = None) -> None:
        destino = Path(caminho) if caminho else self.arquivo_json
        payload = {chave: roi.to_dict() for chave, roi in self.rois.items()}
        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def carregar(self, caminho: Optional[str] = None) -> None:
        origem = Path(caminho) if caminho else self.arquivo_json
        try:
            with open(origem, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.rois = {chave: ROI.from_dict(val) for chave, val in data.items()}
            # Garante que as 3 chaves essenciais existam
            padroes = ["via_a", "via_b", "pedestre"]
            for p in padroes:
                if p not in self.rois:
                    self._criar_rois_padrao()
                    self.salvar(origem)
                    break
        except Exception:
            self._criar_rois_padrao()
            self.salvar(origem)

    def processar_deteccoes(
        self,
        deteccoes: List[Dict[str, Any]],
        largura_frame: int,
        altura_frame: int,
    ) -> Dict[str, Any]:
        """
        Analisa a lista de detecções e calcula a ocupação de cada ROI.

        Cada detecção deve ter:
        - 'bbox': (x1, y1, x2, y2)
        - 'cls_name': str ('carro_de_brinquedo', 'boneco_de_brinquedo', etc)
        """
        carros_via_a = 0
        carros_via_b = 0
        pedestres_faixa = 0

        contagem_por_roi: Dict[str, Dict[str, int]] = {
            chave: {"carros": 0, "pedestres": 0} for chave in self.rois
        }

        for det in deteccoes:
            bbox = det.get("bbox")
            if not bbox:
                continue

            x1, y1, x2, y2 = bbox
            # Ponto de apoio do objeto no chão: centro inferior da bounding box
            ponto_contato_x = (x1 + x2) / 2.0
            ponto_contato_y = float(y2)

            nome_classe = str(det.get("cls_name", "")).lower()
            eh_carro = "carro" in nome_classe or "car" in nome_classe or "veiculo" in nome_classe
            eh_pedestre = "boneco" in nome_classe or "pedestre" in nome_classe or "person" in nome_classe

            for chave_roi, roi in self.rois.items():
                if roi.contem_ponto(ponto_contato_x, ponto_contato_y, largura_frame, altura_frame):
                    if eh_carro:
                        contagem_por_roi[chave_roi]["carros"] += 1
                        if chave_roi == "via_a":
                            carros_via_a += 1
                        elif chave_roi == "via_b":
                            carros_via_b += 1
                    elif eh_pedestre:
                        contagem_por_roi[chave_roi]["pedestres"] += 1
                        if chave_roi == "pedestre":
                            pedestres_faixa += 1

        return {
            "carros_via_a": carros_via_a,
            "carros_via_b": carros_via_b,
            "pedestre_detectado": pedestres_faixa > 0,
            "pedestres_contagem": pedestres_faixa,
            "contagem_detalhada": contagem_por_roi,
        }
