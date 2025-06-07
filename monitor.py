# monitor.py - Versão corrigida com logs detalhados
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import time
import logging
import sys
import signal
from typing import Optional, Dict, Any, List
import traceback

# Imports do Telegram e configurações
from telegram_notifier import TelegramNotifier
from config import (
    MOEDAS, TIMEFRAME, INTERVALO_VERIFICACAO, FORCA_MINIMA_CRUZAMENTO,
    PERIODOS_MA, BINANCE_API, REQUEST_CONFIG,
    FORMATO_PRECO, SIMBOLOS, LOGGING_CONFIG,
    ESTRATEGIA_ATUAL, get_estrategia_info, TELEGRAM_CONFIG
)

# Configuração do logging mais detalhada
logging.basicConfig(
    level=getattr(logging, LOGGING_CONFIG['level']),
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

class MonitorBinanceFutures:
    def __init__(self):
        self.base_url = BINANCE_API['base_url']
        self.ultimos_alertas = {}
        self.alertas_ativos = {}
        self.running = True
        self.stats = {
            'requests_ok': 0,
            'requests_error': 0,
            'alertas_enviados': 0,
            'tempo_inicio': datetime.now()
        }
        
        # Carrega informações da estratégia
        self.estrategia = get_estrategia_info()
        self.ma_principal = self.estrategia['ma_principal']
        self.mas_referencia = self.estrategia['mas_referencia']
        
        logger.info(f"🎯 Estratégia carregada: {self.estrategia['descricao']}")

        # Inicialização do Telegram com logs detalhados
        self.telegram = None
        if TELEGRAM_CONFIG['ativado'] and TELEGRAM_CONFIG['bot_token'] != 'SEU_BOT_TOKEN_AQUI':
            try:
                self.telegram = TelegramNotifier(
                    TELEGRAM_CONFIG['bot_token'], 
                    TELEGRAM_CONFIG['chat_id']
                )
                logger.info("✅ Telegram inicializado com sucesso")
            except Exception as e:
                logger.error(f"❌ Erro ao inicializar Telegram: {e}")
                logger.error(traceback.format_exc())
        else:
            logger.warning("⚠️ Telegram não configurado ou desativado")

        # Setup para encerramento gracioso
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handler para encerramento gracioso"""
        logger.info(f"🛑 Recebido sinal {signum}. Encerrando graciosamente...")
        self.running = False

    def buscar_dados(self, moeda: str) -> Optional[pd.DataFrame]:
        """Busca dados de futuros da Binance com logs detalhados"""
        max_retries = 3
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        }
        
        for tentativa in range(max_retries):
            try:
                url = f"{self.base_url}{BINANCE_API['klines_endpoint']}"
                params = {
                    'symbol': moeda,
                    'interval': TIMEFRAME,
                    'limit': REQUEST_CONFIG['limit_candles']
                }
                
                logger.debug(f"📡 Buscando dados para {moeda} (tentativa {tentativa + 1})")
                
                response = requests.get(
                    url, 
                    params=params, 
                    headers=headers,
                    timeout=REQUEST_CONFIG['timeout']
                )
                
                # Log detalhado do status da response
                logger.debug(f"📊 {moeda}: Status {response.status_code}, Size: {len(response.content)} bytes")
                
                if response.status_code == 451:
                    wait_time = (tentativa + 1) * 5
                    logger.warning(f"⚠️ {moeda}: Rate limit (451), aguardando {wait_time}s")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 429:
                    wait_time = (tentativa + 1) * 10
                    logger.warning(f"⚠️ {moeda}: Too many requests (429), aguardando {wait_time}s")
                    time.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                
                # Validação da resposta
                data = response.json()
                if not data or not isinstance(data, list):
                    logger.error(f"❌ {moeda}: Resposta inválida da API - {data}")
                    continue
                
                if len(data) < max(PERIODOS_MA.values()):
                    logger.error(f"❌ {moeda}: Dados insuficientes - {len(data)} candles, necessário {max(PERIODOS_MA.values())}")
                    continue
                
                df = pd.DataFrame(data, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_asset_volume', 'number_of_trades',
                    'taker_buy_base', 'taker_buy_quote', 'ignore'
                ])
                
                # Conversão com validação
                try:
                    df['close'] = pd.to_numeric(df['close'], errors='coerce')
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', errors='coerce')
                    
                    # Verifica se há valores NaN
                    if df['close'].isna().any() or df['timestamp'].isna().any():
                        logger.error(f"❌ {moeda}: Dados contêm valores inválidos (NaN)")
                        continue
                        
                except Exception as e:
                    logger.error(f"❌ {moeda}: Erro na conversão de dados - {e}")
                    continue
                
                self.stats['requests_ok'] += 1
                logger.debug(f"✅ {moeda}: Dados obtidos com sucesso - {len(df)} candles")
                return df
                
            except requests.exceptions.Timeout:
                logger.warning(f"⏱️ {moeda}: Timeout na tentativa {tentativa + 1}")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"🌐 {moeda}: Erro de conexão na tentativa {tentativa + 1} - {e}")
            except requests.exceptions.HTTPError as e:
                logger.error(f"🚫 {moeda}: Erro HTTP na tentativa {tentativa + 1} - {e}")
            except Exception as e:
                logger.error(f"❌ {moeda}: Erro inesperado na tentativa {tentativa + 1} - {e}")
                logger.error(traceback.format_exc())
            
            if tentativa < max_retries - 1:
                wait_time = (tentativa + 1) * 2
                logger.info(f"⏳ {moeda}: Aguardando {wait_time}s antes da próxima tentativa")
                time.sleep(wait_time)
        
        self.stats['requests_error'] += 1
        logger.error(f"💀 {moeda}: Falha após {max_retries} tentativas")
        return None

    def calcular_medias(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula as médias móveis com validação"""
        try:
            if len(df) < max(PERIODOS_MA.values()):
                logger.error(f"❌ Dados insuficientes para calcular MAs: {len(df)} < {max(PERIODOS_MA.values())}")
                return None
            
            for nome, periodo in PERIODOS_MA.items():
                if len(df) >= periodo:
                    df[nome] = df['close'].rolling(periodo).mean()
                else:
                    logger.warning(f"⚠️ Período {periodo} maior que dados disponíveis {len(df)}")
                    return None
            
            # Retorna apenas os 2 últimos registros válidos
            dados_recentes = df.iloc[-2:].copy()
            
            # Verifica se há valores NaN nas MAs
            for nome in PERIODOS_MA.keys():
                if dados_recentes[nome].isna().any():
                    logger.warning(f"⚠️ MA {nome} contém valores NaN")
                    return None
            
            return dados_recentes
            
        except Exception as e:
            logger.error(f"❌ Erro ao calcular médias: {e}")
            logger.error(traceback.format_exc())
            return None

    def detectar_cruzamento(self, dados_recentes: pd.DataFrame) -> tuple:
        """Detecta cruzamentos com logs detalhados"""
        try:
            if dados_recentes is None or len(dados_recentes) < 2:
                return None, None
                
            anterior = dados_recentes.iloc[0]
            atual = dados_recentes.iloc[1]
            
            # Verifica se todas as MAs necessárias existem
            mas_necessarias = [self.ma_principal] + self.mas_referencia
            for ma in mas_necessarias:
                if ma not in atual or ma not in anterior:
                    logger.warning(f"⚠️ MA {ma} não encontrada nos dados")
                    return None, None
                if pd.isna(atual[ma]) or pd.isna(anterior[ma]):
                    logger.warning(f"⚠️ MA {ma} contém valores NaN")
                    return None, None
            
            ma_principal_atual = atual[self.ma_principal]
            ma_principal_anterior = anterior[self.ma_principal]
            
            logger.debug(f"🔍 MA Principal: {ma_principal_atual:.6f} (anterior: {ma_principal_anterior:.6f})")
            
            # CRUZAMENTO DE ALTA: MA_principal deve estar X% ACIMA de TODAS as MAs de referência
            cruzamento_alta_forte = True
            for ma_ref in self.mas_referencia:
                limite_superior = atual[ma_ref] * (1 + FORCA_MINIMA_CRUZAMENTO)
                logger.debug(f"🔍 {ma_ref}: {atual[ma_ref]:.6f}, Limite: {limite_superior:.6f}")
                if ma_principal_atual <= limite_superior:
                    cruzamento_alta_forte = False
                    break
            
            # CRUZAMENTO DE BAIXA: MA_principal deve estar X% ABAIXO de TODAS as MAs de referência  
            cruzamento_baixa_forte = True
            for ma_ref in self.mas_referencia:
                limite_inferior = atual[ma_ref] * (1 - FORCA_MINIMA_CRUZAMENTO)
                if ma_principal_atual >= limite_inferior:
                    cruzamento_baixa_forte = False
                    break
            
            # Verifica se houve CRUZAMENTO (mudança de posição entre anterior e atual)
            if cruzamento_alta_forte:
                cruzou_de_fato = any(
                    anterior[self.ma_principal] <= anterior[ma_ref] 
                    for ma_ref in self.mas_referencia
                )
                cruzamento_alta_forte = cruzou_de_fato
                if cruzou_de_fato:
                    logger.info(f"🟢 Cruzamento de ALTA detectado!")
            
            if cruzamento_baixa_forte:
                cruzou_de_fato = any(
                    anterior[self.ma_principal] >= anterior[ma_ref] 
                    for ma_ref in self.mas_referencia
                )
                cruzamento_baixa_forte = cruzou_de_fato
                if cruzou_de_fato:
                    logger.info(f"🔴 Cruzamento de BAIXA detectado!")
            
            return cruzamento_alta_forte, cruzamento_baixa_forte
            
        except Exception as e:
            logger.error(f"❌ Erro ao detectar cruzamento: {e}")
            logger.error(traceback.format_exc())
            return None, None

    def verificar_cruzamento(self, moeda: str) -> Optional[Dict[str, Any]]:
        """Verifica cruzamentos de médias com logs completos"""
        try:
            logger.debug(f"🔍 Verificando {moeda}...")
            
            dados = self.buscar_dados(moeda)
            if dados is None:
                logger.error(f"❌ {moeda}: Falha ao buscar dados")
                return None
            
            if len(dados) < max(PERIODOS_MA.values()):
                logger.error(f"❌ {moeda}: Dados insuficientes {len(dados)} < {max(PERIODOS_MA.values())}")
                return None
                
            dados_recentes = self.calcular_medias(dados)
            if dados_recentes is None:
                logger.error(f"❌ {moeda}: Falha ao calcular médias")
                return None
                
            atual = dados_recentes.iloc[-1]
            
            cruzamento_alta, cruzamento_baixa = self.detectar_cruzamento(dados_recentes)
            
            if cruzamento_alta is None and cruzamento_baixa is None:
                logger.debug(f"⚪ {moeda}: Nenhum cruzamento detectado")
                return None
            
            # Controle de alertas repetidos
            chave_alerta = f"{moeda}_{TIMEFRAME}"
            
            # Reset do alerta se as condições mudaram
            if chave_alerta in self.alertas_ativos:
                ma_principal_atual = atual[self.ma_principal]
                tem_forca = False
                
                for ma_ref in self.mas_referencia:
                    if ma_ref in atual:
                        limite_superior = atual[ma_ref] * (1 + FORCA_MINIMA_CRUZAMENTO)
                        limite_inferior = atual[ma_ref] * (1 - FORCA_MINIMA_CRUZAMENTO)
                        
                        if (ma_principal_atual > limite_superior or ma_principal_atual < limite_inferior):
                            tem_forca = True
                            break
                
                if not tem_forca:
                    logger.info(f"🔄 {moeda}: Reset de alerta - força insuficiente")
                    del self.alertas_ativos[chave_alerta]
            
            # Só alerta se detectou cruzamento E não alertou recentemente
            if (cruzamento_alta or cruzamento_baixa) and chave_alerta not in self.alertas_ativos:
                tipo_alerta = 'alta' if cruzamento_alta else 'baixa'
                logger.info(f"🚨 {moeda}: ALERTA DE {tipo_alerta.upper()} CONFIRMADO!")
                
                self.alertas_ativos[chave_alerta] = {
                    'tipo': tipo_alerta,
                    'timestamp': datetime.now()
                }
                
                resultado = {
                    'moeda': moeda,
                    'preco': atual['close'],
                    'cruzamento_alta': cruzamento_alta,
                    'cruzamento_baixa': cruzamento_baixa,
                    'timestamp': atual['timestamp']
                }
                
                # Adiciona todas as MAs ao resultado
                for nome in PERIODOS_MA.keys():
                    resultado[nome.lower()] = atual[nome]
                
                # Envia notificação Telegram
                if self.telegram:
                    try:
                        sucesso = self.telegram.enviar_alerta(resultado)
                        if sucesso:
                            self.stats['alertas_enviados'] += 1
                            logger.info(f"✅ {moeda}: Telegram enviado com sucesso")
                        else:
                            logger.error(f"❌ {moeda}: Falha ao enviar Telegram")
                    except Exception as e:
                        logger.error(f"❌ {moeda}: Erro no Telegram - {e}")
                
                return resultado
            
            logger.debug(f"⚪ {moeda}: Sem novos alertas")
            return None
            
        except Exception as e:
            logger.error(f"💀 {moeda}: ERRO CRÍTICO - {e}")
            logger.error(traceback.format_exc())
            return None

    def mostrar_alertas(self, resultados: List[Dict[str, Any]]) -> None:
        """Exibe alertas formatados com stats"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        alertas_encontrados = [r for r in resultados if r is not None]
        
        if alertas_encontrados:
            print(f"\n{'='*60}")
            print(f"🚨 ALERTAS DETECTADOS | {timestamp}")
            print(f"📈 Estratégia: {self.estrategia['descricao']}")
            print("="*60)
            
            for r in alertas_encontrados:
                tipo = "ALTA" if r['cruzamento_alta'] else "BAIXA"
                emoji = SIMBOLOS['alta'] if r['cruzamento_alta'] else SIMBOLOS['baixa']
                
                print(f"\n{emoji} {tipo}: {r['moeda']} | Preço: ${r['preco']:.{FORMATO_PRECO['decimais']}f}")
                print(f"   Horário: {r['timestamp']}")
                
                # MAs info
                mas_info = []
                mas_ordenadas = sorted(PERIODOS_MA.items(), key=lambda x: x[1])
                for nome, periodo in mas_ordenadas:
                    valor = r[nome.lower()]
                    mas_info.append(f"{nome}: {valor:.{FORMATO_PRECO['decimais']}f}")
                print(f"   {' | '.join(mas_info)}")
        else:
            # Log com estatísticas
            uptime = datetime.now() - self.stats['tempo_inicio']
            uptime_str = str(uptime).split('.')[0]  # Remove microssegundos
            
            status = f"✅ Monitor ativo | {timestamp} | Uptime: {uptime_str}"
            if self.alertas_ativos:
                status += f" | Alertas ativos: {len(self.alertas_ativos)}"
            
            # Stats a cada 12 verificações (1 hora se intervalo = 5min)
            if self.stats['requests_ok'] % 12 == 0 and self.stats['requests_ok'] > 0:
                total_requests = self.stats['requests_ok'] + self.stats['requests_error']
                success_rate = (self.stats['requests_ok'] / total_requests * 100) if total_requests > 0 else 0
                status += f" | Sucesso: {success_rate:.1f}% | Alertas: {self.stats['alertas_enviados']}"
            
            print(status)

    def executar_verificacao(self) -> None:
        """Executa verificação paralela com logs detalhados"""
        try:
            logger.debug(f"🔄 Iniciando verificação de {len(MOEDAS)} moedas...")
            inicio = time.time()
            
            with ThreadPoolExecutor(max_workers=len(MOEDAS)) as executor:
                # Submete todas as tasks
                future_to_moeda = {
                    executor.submit(self.verificar_cruzamento, moeda): moeda 
                    for moeda in MOEDAS
                }
                
                resultados = []
                
                # Processa resultados conforme completam
                for future in as_completed(future_to_moeda, timeout=60):
                    moeda = future_to_moeda[future]
                    try:
                        resultado = future.result(timeout=30)
                        resultados.append(resultado)
                        logger.debug(f"✅ {moeda}: Processado")
                    except Exception as e:
                        logger.error(f"💀 {moeda}: ERRO - {e}")
                        resultados.append(None)
                
                tempo_execucao = time.time() - inicio
                logger.debug(f"⏱️ Verificação concluída em {tempo_execucao:.2f}s")
                
                self.mostrar_alertas(resultados)
                
        except Exception as e:
            logger.error(f"💀 ERRO CRÍTICO na verificação: {e}")
            logger.error(traceback.format_exc())

    def iniciar_monitoramento(self) -> None:
        """Inicia o loop de monitoramento com logs detalhados"""
        print("\033[1m" + "="*60)
        print(f"🚀 MONITOR ONLINE - FUTUROS BINANCE")
        print("="*60 + "\033[0m")
        print(f"📈 Moedas: {', '.join(MOEDAS)}")
        print(f"⏱️  Timeframe: {TIMEFRAME}")
        print(f"🔄 Intervalo: {INTERVALO_VERIFICACAO} segundos")
        print(f"📏 Força mínima: {FORCA_MINIMA_CRUZAMENTO*100:.1f}%")
        print(f"🎯 Estratégia: {self.estrategia['descricao']}")
        print(f"📊 MAs: {dict(PERIODOS_MA)}")
        print(f"🤖 Telegram: {'✅ Ativo' if self.telegram else '❌ Inativo'}")
        print(f"🔍 Log Level: {LOGGING_CONFIG['level']}")
        print("\n🌐 Monitor rodando na nuvem...\n")
        
        tentativas_erro = 0
        max_tentativas = 5
        
        try:
            while self.running:
                try:
                    logger.debug("🔄 Iniciando ciclo de verificação...")
                    inicio = time.time()
                    
                    self.executar_verificacao()
                    
                    # Reset contador de erros
                    tentativas_erro = 0
                    
                    tempo_execucao = time.time() - inicio
                    tempo_espera = max(0, INTERVALO_VERIFICACAO - tempo_execucao)
                    
                    if tempo_espera > 0 and self.running:
                        logger.debug(f"⏳ Aguardando {tempo_espera:.0f}s...")
                        time.sleep(tempo_espera)
                    
                except Exception as e:
                    tentativas_erro += 1
                    logger.error(f"💀 ERRO na execução ({tentativas_erro}/{max_tentativas}): {e}")
                    logger.error(traceback.format_exc())
                    
                    if tentativas_erro >= max_tentativas:
                        logger.critical("💀 MUITOS ERROS CONSECUTIVOS - Reiniciando aplicação...")
                        break
                    
                    wait_time = min(60, tentativas_erro * 10)
                    logger.info(f"⏳ Aguardando {wait_time}s antes de tentar novamente...")
                    time.sleep(wait_time)
                
        except KeyboardInterrupt:
            logger.info("🛑 Interrupção por teclado")
        finally:
            self._mostrar_resumo_final()

    def _mostrar_resumo_final(self):
        """Mostra resumo final da execução"""
        uptime = datetime.now() - self.stats['tempo_inicio']
        total_requests = self.stats['requests_ok'] + self.stats['requests_error']
        success_rate = (self.stats['requests_ok'] / total_requests * 100) if total_requests > 0 else 0
        
        print(f"\n🛑 MONITOR ENCERRADO")
        print(f"📊 RESUMO FINAL:")
        print(f"   • Tempo ativo: {str(uptime).split('.')[0]}")
        print(f"   • Requests OK: {self.stats['requests_ok']}")
        print(f"   • Requests Erro: {self.stats['requests_error']}")
        print(f"   • Taxa de sucesso: {success_rate:.1f}%")
        print(f"   • Alertas enviados: {self.stats['alertas_enviados']}")
        print(f"   • Alertas ativos: {len(self.alertas_ativos)}")
        print(f"   • Estratégia: {self.estrategia['descricao']}")