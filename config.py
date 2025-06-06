# config.py - Todas as configurações centralizadas
import os
from typing import List, Dict, Any, Tuple

# Carrega variáveis do arquivo .env se existir
def carregar_env():
    """Carrega variáveis do arquivo .env"""
    try:
        with open('.env', 'r') as f:
            for linha in f:
                linha = linha.strip()
                if linha and not linha.startswith('#') and '=' in linha:
                    chave, valor = linha.split('=', 1)
                    os.environ[chave.strip()] = valor.strip()
    except FileNotFoundError:
        print("⚠️  Arquivo .env não encontrado. Usando configurações padrão.")

# Carrega as variáveis
carregar_env()

# =============================================================================
# CONFIGURAÇÕES PRINCIPAIS
# =============================================================================

TELEGRAM_CONFIG = {
    'bot_token': os.getenv('BOT_TOKEN', 'SEU_BOT_TOKEN_AQUI'),
    'chat_id': os.getenv('CHAT_ID', 'SEU_CHAT_ID_AQUI'),
    'ativado': True
}

# Moedas para monitorar
MOEDAS: List[str] = [
    "BTCUSDT", "ETHUSDT", "ADAUSDT", "SOLUSDT", 
    "AVAXUSDT", "DOGEUSDT", "XRPUSDT"
]

# Timeframe para análise
TIMEFRAME: str = '4h'  # 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d

# Intervalo entre verificações (segundos)
INTERVALO_VERIFICACAO: int = 60  # 5 minutos

# Força mínima do cruzamento - MA principal deve estar X% acima/abaixo das MAs de referência
FORCA_MINIMA_CRUZAMENTO: float = 0.02  # 2% - força mínima para validar o cruzamento

# =============================================================================
# BANCO DE MÉDIAS MÓVEIS DISPONÍVEIS
# =============================================================================

# Todas as MAs disponíveis para uso
MAS_DISPONIVEIS: Dict[str, int] = {
    'MA_5': 5, 'MA_7': 7, 'MA_9': 9, 'MA_12': 12, 'MA_20': 20,
    'MA_25': 25, 'MA_30': 30, 'MA_50': 50, 'MA_99': 99, 
    'MA_100': 100, 'MA_150': 150, 'MA_200': 200
}

# =============================================================================
# CONFIGURAÇÕES DE ESTRATÉGIAS DE CRUZAMENTO
# =============================================================================

# ✨ FÁCIL DE MODIFICAR - ESCOLHA SUA ESTRATÉGIA AQUI ✨

# Estratégia 1: MA Rápida cruzando múltiplas MAs (ATUAL)
ESTRATEGIA_ATUAL = {
    'nome': 'MA_RAPIDA_vs_MULTIPLAS',
    'ma_principal': 'MA_7',      # ← A MA que vai cruzar as outras
    'mas_referencia': ['MA_25', 'MA_99'],  # ← MAs que serão cruzadas
    'descricao': 'MA7 cruzando MA25 e MA99'
}

# =============================================================================
# PROCESSAMENTO AUTOMÁTICO DA ESTRATÉGIA
# =============================================================================

def get_mas_necessarias() -> Dict[str, int]:
    """Retorna apenas as MAs necessárias para a estratégia atual"""
    mas_necessarias = {}
    
    # Adiciona a MA principal
    ma_principal = ESTRATEGIA_ATUAL['ma_principal']
    if ma_principal in MAS_DISPONIVEIS:
        mas_necessarias[ma_principal] = MAS_DISPONIVEIS[ma_principal]
    
    # Adiciona as MAs de referência
    for ma_ref in ESTRATEGIA_ATUAL['mas_referencia']:
        if ma_ref in MAS_DISPONIVEIS:
            mas_necessarias[ma_ref] = MAS_DISPONIVEIS[ma_ref]
    
    return mas_necessarias

# MAs que serão calculadas (baseado na estratégia escolhida)
PERIODOS_MA = get_mas_necessarias()

# =============================================================================
# CONFIGURAÇÕES DA API BINANCE
# =============================================================================

# URL da API
BINANCE_API: Dict[str, str] = {
    'base_url': 'https://fapi.binance.com',
    'klines_endpoint': '/fapi/v1/klines'
}

# Configurações da requisição
REQUEST_CONFIG: Dict[str, Any] = {
    'timeout': 10,  # ← Tempo limite para requisição (10 segundos)
    'limit_candles': 100
}

# =============================================================================
# CONFIGURAÇÕES DE DISPLAY
# =============================================================================

# Formatação de preços
FORMATO_PRECO: Dict[str, Any] = {
    'decimais': 6,
    'mostrar_simbolo': True
}

# Cores e símbolos para alertas
SIMBOLOS: Dict[str, str] = {
    'alta': '🟢',
    'baixa': '🔴',
    'neutro': '✅',
    'alerta': '🎯',
    'tempo': '⏳',
    'config': '⚙️',
    'stop': '✋',
    'resumo': '📊'
}

# =============================================================================
# LOGGING
# =============================================================================

LOGGING_CONFIG: Dict[str, Any] = {
    'level': 'INFO',
    'format': '%(asctime)s - %(message)s',
    'datefmt': '%H:%M:%S'
}

# =============================================================================
# FUNÇÕES AUXILIARES DE CONFIGURAÇÃO
# =============================================================================

def get_ma_names() -> List[str]:
    """Retorna os nomes das MAs configuradas"""
    return list(PERIODOS_MA.keys())

def get_ma_periods() -> List[int]:
    """Retorna os períodos das MAs configuradas"""
    return list(PERIODOS_MA.values())

def get_estrategia_info() -> Dict[str, Any]:
    """Retorna informações da estratégia atual"""
    return {
        'nome': ESTRATEGIA_ATUAL['nome'],
        'ma_principal': ESTRATEGIA_ATUAL['ma_principal'],
        'mas_referencia': ESTRATEGIA_ATUAL['mas_referencia'],
        'descricao': ESTRATEGIA_ATUAL['descricao'],
        'periodo_principal': MAS_DISPONIVEIS.get(ESTRATEGIA_ATUAL['ma_principal'], 0),
        'periodos_referencia': [MAS_DISPONIVEIS.get(ma, 0) for ma in ESTRATEGIA_ATUAL['mas_referencia']]
    }

def criar_nova_estrategia(nome: str, ma_principal: str, mas_referencia: List[str], descricao: str = "") -> Dict[str, Any]:
    """
    Cria uma nova estratégia personalizada
    
    Exemplo de uso:
    nova_estrategia = criar_nova_estrategia(
        nome='MINHA_ESTRATEGIA',
        ma_principal='MA_20',
        mas_referencia=['MA_50', 'MA_200'],
        descricao='MA20 cruzando MA50 e MA200'
    )
    """
    return {
        'nome': nome,
        'ma_principal': ma_principal,
        'mas_referencia': mas_referencia,
        'descricao': descricao if descricao else f"{ma_principal} cruzando {', '.join(mas_referencia)}"
    }

def adicionar_nova_ma(nome: str, periodo: int) -> None:
    """Adiciona uma nova MA ao banco disponível"""
    MAS_DISPONIVEIS[nome] = periodo
    # Recalcula as MAs necessárias
    global PERIODOS_MA
    PERIODOS_MA = get_mas_necessarias()

def listar_estrategias_exemplo() -> List[Dict[str, Any]]:
    """Lista exemplos de estratégias que podem ser usadas"""
    return [
        criar_nova_estrategia('CLASSICA_20_50', 'MA_20', ['MA_50'], 'Cruzamento clássico'),
        criar_nova_estrategia('GOLDEN_CROSS', 'MA_50', ['MA_200'], 'Golden Cross'),
        criar_nova_estrategia('RAPIDA_TRIPLA', 'MA_9', ['MA_25', 'MA_99'], 'MA9 vs MA25 e MA99'),
        criar_nova_estrategia('SCALPING', 'MA_5', ['MA_20'], 'Scalping MA5 vs MA20'),
        criar_nova_estrategia('SWING_TRADE', 'MA_20', ['MA_50', 'MA_200'], 'Swing trade múltiplas MAs')
    ]

def update_moedas(novas_moedas: List[str]) -> None:
    """Atualiza a lista de moedas"""
    global MOEDAS
    MOEDAS = novas_moedas

def get_config_summary() -> Dict[str, Any]:
    """Retorna um resumo das configurações atuais"""
    estrategia = get_estrategia_info()
    return {
        'moedas': len(MOEDAS),
        'timeframe': TIMEFRAME,
        'intervalo': INTERVALO_VERIFICACAO,
        'limite_distancia': f"{FORCA_MINIMA_CRUZAMENTO*100:.1f}%",
        'estrategia': estrategia['descricao'],
        'ma_principal': f"{estrategia['ma_principal']}({estrategia['periodo_principal']})",
        'mas_referencia': [f"{ma}({periodo})" for ma, periodo in zip(estrategia['mas_referencia'], estrategia['periodos_referencia'])],
        'medias_moveis': PERIODOS_MA,
        'mas_disponiveis': len(MAS_DISPONIVEIS)
    }

# =============================================================================
# VALIDAÇÃO AUTOMÁTICA
# =============================================================================

def validar_configuracao() -> Tuple[bool, str]:
    """Valida se a configuração atual é válida"""
    ma_principal = ESTRATEGIA_ATUAL['ma_principal']
    mas_referencia = ESTRATEGIA_ATUAL['mas_referencia']
    
    # Verifica se MA principal existe
    if ma_principal not in MAS_DISPONIVEIS:
        return False, f"MA principal '{ma_principal}' não encontrada em MAS_DISPONIVEIS"
    
    # Verifica se todas as MAs de referência existem
    for ma_ref in mas_referencia:
        if ma_ref not in MAS_DISPONIVEIS:
            return False, f"MA de referência '{ma_ref}' não encontrada em MAS_DISPONIVEIS"
    
    # Verifica se há pelo menos uma MA de referência
    if not mas_referencia:
        return False, "É necessário pelo menos uma MA de referência"
    
    # Verifica se as MAs têm períodos diferentes
    periodo_principal = MAS_DISPONIVEIS[ma_principal]
    for ma_ref in mas_referencia:
        if MAS_DISPONIVEIS[ma_ref] == periodo_principal:
            return False, f"MA principal e MA de referência '{ma_ref}' têm o mesmo período ({periodo_principal})"
    
    return True, "Configuração válida"

# Validação automática na importação
_is_valid, _error_msg = validar_configuracao()
if not _is_valid:
    print(f"⚠️  ERRO DE CONFIGURAÇÃO: {_error_msg}")
    print("Por favor, corrija a configuração em ESTRATEGIA_ATUAL")
else:
    print(f"✅ Configuração válida: {ESTRATEGIA_ATUAL['descricao']}")

# Verifica se credenciais do Telegram estão configuradas
if TELEGRAM_CONFIG['bot_token'] == 'SEU_BOT_TOKEN_AQUI':
    print("⚠️  Configure o BOT_TOKEN no arquivo .env")
if TELEGRAM_CONFIG['chat_id'] == 'SEU_CHAT_ID_AQUI':
    print("⚠️  Configure o CHAT_ID no arquivo .env")