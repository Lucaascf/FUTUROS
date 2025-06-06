# main.py - Arquivo principal para executar o monitor
from monitor import MonitorBinanceFutures
from config import (
    TIMEFRAME, MOEDAS, INTERVALO_VERIFICACAO, FORCA_MINIMA_CRUZAMENTO,
    PERIODOS_MA, get_config_summary, SIMBOLOS, get_estrategia_info,
    listar_estrategias_exemplo
)

def main():
    """Função principal"""
    # Inicia o monitor diretamente
    monitor = MonitorBinanceFutures()
    monitor.iniciar_monitoramento()

if __name__ == "__main__":
    main()