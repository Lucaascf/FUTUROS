# monitor.py - Versão otimizada para Railway
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import time
import logging
import sys
import signal
from typing import Optional, Dict, Any, List

# Imports do Telegram e configurações
from telegram_notifier import TelegramNotifier
from config import (
    MOEDAS, TIMEFRAME, INTERVALO_VERIFICACAO, FORCA_MINIMA_CRUZAMENTO,
    PERIODOS_MA, BINANCE_API, REQUEST_CONFIG,
    FORMATO_PRECO, SIMBOLOS, LOGGING_CONFIG,
    ESTRATEGIA_ATUAL, get_estrategia_info, TELEGRAM_CONFIG
)

# Configuração do logging otimizada para Railway
logging.basicConfig(
    level=getattr(logging, LOGGING_CONFIG['level']),
    format=LOGGING_CONFIG['format'],
    datefmt=LOGGING_CONFIG['datefmt'],
    handlers=[logging.StreamHandler(sys.stdout)]
)

class MonitorBinanceFutures:
    def __init__(self):
        self.base_url = BINANCE_API['base_url']
        self.ultimos_alertas = {}
        self.alertas_ativos = {}
        self.running = True
        
        # Carrega informações da estratégia
        self.estrategia = get_estrategia_info()
        self.ma_principal = self.estrategia['ma_principal']
        self.mas_referencia = self.estrategia['mas_referencia']
        
        print(f"🎯 Estratégia carregada: {self.estrategia['descricao']}")

        self.telegram = None
        if TELEGRAM_CONFIG['ativado'] and TELEGRAM_CONFIG['bot_token'] != 'SEU_BOT_TOKEN_AQUI':
            self.telegram = TelegramNotifier(
                TELEGRAM_CONFIG['bot_token'], 
                TELEGRAM_CONFIG['chat_id']
            )

        # Setup para encerramento gracioso
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handler para encerramento gracioso"""
        print(f"\n🛑 Recebido sinal {signum}. Encerrando...")
        self.running = False

    def buscar_dados(self, moeda: str) -> Optional[pd.DataFrame]:
        """Busca dados de futuros da Binance com retry"""
        max_retries = 3
        
        for tentativa in range(max_retries):
            try:
                url = f"{self.base_url}{BINANCE_API['klines_endpoint']}"
                params = {
                    'symbol': moeda,
                    'interval': TIMEFRAME,
                    'limit': REQUEST_CONFIG['limit_candles']
                }
                
                response = requests.get(
                    url, 
                    params=params, 
                    timeout=REQUEST_CONFIG['timeout']
                )
                response.raise_for_status()
                
                df = pd.DataFrame(response.json(), columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_asset_volume', 'number_of_trades',
                    'taker_buy_base', 'taker_buy_quote', 'ignore'
                ])
                
                df['close'] = df['close'].astype(float)
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                return df
                
            except Exception as e:
                logging.warning(f"Tentativa {tentativa + 1}/{max_retries} falhou para {moeda}: {str(e)}")
                if tentativa == max_retries - 1:
                    logging.error(f"Erro final ao buscar {moeda}: {str(e)}")
                else:
                    time.sleep(1)
                    
        return None

    def calcular_medias(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula as médias móveis dinamicamente baseado na estratégia"""
        for nome, periodo in PERIODOS_MA.items():
            df[nome] = df['close'].rolling(periodo).mean()
        
        return df.iloc[-2:].copy()

    def detectar_cruzamento(self, dados_recentes: pd.DataFrame) -> tuple:
        """Detecta cruzamentos com FORÇA suficiente baseado na estratégia configurada"""
        if len(dados_recentes) < 2:
            return None, None
            
        anterior = dados_recentes.iloc[0]
        atual = dados_recentes.iloc[1]
        
        # Verifica se todas as MAs necessárias existem
        mas_necessarias = [self.ma_principal] + self.mas_referencia
        for ma in mas_necessarias:
            if ma not in atual or ma not in anterior:
                return None, None
        
        ma_principal_atual = atual[self.ma_principal]
        
        # CRUZAMENTO DE ALTA: MA_principal deve estar X% ACIMA de TODAS as MAs de referência
        cruzamento_alta_forte = True
        for ma_ref in self.mas_referencia:
            limite_superior = atual[ma_ref] * (1 + FORCA_MINIMA_CRUZAMENTO)
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
        
        if cruzamento_baixa_forte:
            cruzou_de_fato = any(
                anterior[self.ma_principal] >= anterior[ma_ref] 
                for ma_ref in self.mas_referencia
            )
            cruzamento_baixa_forte = cruzou_de_fato
        
        return cruzamento_alta_forte, cruzamento_baixa_forte

    def verificar_cruzamento(self, moeda: str) -> Optional[Dict[str, Any]]:
        """Verifica cruzamentos de médias"""
        dados = self.buscar_dados(moeda)
        if dados is None or len(dados) < max(PERIODOS_MA.values()):
            return None
            
        dados_recentes = self.calcular_medias(dados)
        atual = dados_recentes.iloc[-1]
        
        cruzamento_alta, cruzamento_baixa = self.detectar_cruzamento(dados_recentes)
        
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
                del self.alertas_ativos[chave_alerta]
        
        # Só alerta se detectou cruzamento E não alertou recentemente
        if (cruzamento_alta or cruzamento_baixa) and chave_alerta not in self.alertas_ativos:
            self.alertas_ativos[chave_alerta] = {
                'tipo': 'alta' if cruzamento_alta else 'baixa',
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
                self.telegram.enviar_alerta(resultado)
            
            return resultado
        
        return None

    def mostrar_alertas(self, resultados: List[Dict[str, Any]]) -> None:
        """Exibe alertas formatados - otimizado para Railway"""
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
            # Log mais limpo para Railway
            ativos = len(self.alertas_ativos)
            status = f"✅ Monitorando... | {timestamp}"
            if ativos > 0:
                status += f" | Alertas ativos: {ativos}"
            print(status)

    def executar_verificacao(self) -> None:
        """Executa verificação paralela com timeout"""
        try:
            with ThreadPoolExecutor(max_workers=len(MOEDAS)) as executor:
                futures = {executor.submit(self.verificar_cruzamento, moeda): moeda for moeda in MOEDAS}
                resultados = []
                
                for future in futures:
                    try:
                        resultado = future.result(timeout=30)
                        resultados.append(resultado)
                    except Exception as e:
                        moeda = futures[future]
                        logging.error(f"Erro ao processar {moeda}: {e}")
                        resultados.append(None)
                
                self.mostrar_alertas(resultados)
                
        except Exception as e:
            logging.error(f"Erro na verificação: {e}")

    def iniciar_monitoramento(self) -> None:
        """Inicia o loop de monitoramento - versão Railway"""
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
        print("\n🌐 Monitor rodando na nuvem...\n")
        
        tentativas_erro = 0
        max_tentativas = 5
        
        try:
            while self.running:
                try:
                    inicio = time.time()
                    self.executar_verificacao()
                    
                    # Reset contador de erros
                    tentativas_erro = 0
                    
                    tempo_execucao = time.time() - inicio
                    tempo_espera = max(0, INTERVALO_VERIFICACAO - tempo_execucao)
                    
                    # Sleep simples para Railway (sem contagem regressiva)
                    if tempo_espera > 0 and self.running:
                        print(f"⏳ Aguardando {tempo_espera:.0f}s para próxima verificação...")
                        time.sleep(tempo_espera)
                    
                except Exception as e:
                    tentativas_erro += 1
                    logging.error(f"Erro na execução ({tentativas_erro}/{max_tentativas}): {e}")
                    
                    if tentativas_erro >= max_tentativas:
                        logging.critical("Muitos erros consecutivos. Reiniciando...")
                        break
                    
                    time.sleep(60)
                
        except KeyboardInterrupt:
            pass
        finally:
            print(f"\n🛑 Monitor encerrado")
            print(f"📊 Resumo:")
            print(f"   • Estratégia: {self.estrategia['descricao']}")
            if self.alertas_ativos:
                print(f"   • Alertas gerados: {len(self.alertas_ativos)}")
            else:
                print("   • Nenhum alerta gerado")