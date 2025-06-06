# telegram_notifier.py - Notificações com formatação normal
import requests
from typing import Dict, Any
from config import FORCA_MINIMA_CRUZAMENTO, TIMEFRAME

class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        # Testa conexão na inicialização
        print("🤖 Testando conexão Telegram...")
        if self._testar_conexao():
            print("✅ Telegram conectado!")
        else:
            print("❌ Erro na conexão Telegram")

    def _testar_conexao(self) -> bool:
        """Testa se o bot está funcionando"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            response = requests.get(url, timeout=5)
            return response.status_code == 200 and response.json().get('ok', False)
        except:
            return False

    def _calcular_forca_real(self, resultado: Dict[str, Any]) -> float:
        """Calcula a força real do cruzamento"""
        ma7 = resultado.get('ma_7', 0)
        ma25 = resultado.get('ma_25', 0)
        ma99 = resultado.get('ma_99', 0)
        
        if ma25 == 0 or ma99 == 0:
            return 0
        
        # Calcula distância percentual da MA7 para cada MA de referência
        forca_vs_ma25 = abs((ma7 - ma25) / ma25) * 100
        forca_vs_ma99 = abs((ma7 - ma99) / ma99) * 100
        
        # A força real é a MENOR distância (gargalo)
        return min(forca_vs_ma25, forca_vs_ma99)

    def enviar_alerta(self, resultado: Dict[str, Any]) -> bool:
        """Envia alerta de cruzamento para o Telegram"""
        try:
            # Calcula força real
            forca_real = self._calcular_forca_real(resultado)
            minimo_exigido = FORCA_MINIMA_CRUZAMENTO * 100
            
            # Determina tipo e emoji
            if resultado['cruzamento_alta']:
                emoji = "🟢"
                tipo = "ALTA"
                acao = "LONG"
            else:
                emoji = "🔴"
                tipo = "BAIXA"
                acao = "SHORT"
            
            # Classificação da força
            if forca_real >= minimo_exigido * 2:
                forca_desc = "MUITO FORTE ✅"
            elif forca_real >= minimo_exigido * 1.5:
                forca_desc = "FORTE ✅"
            else:
                forca_desc = "VÁLIDO ✅"
            
            # Mensagem com formatação normal (sem markdown)
            mensagem = f"""{emoji} {resultado['moeda']} - {tipo}

💰 Preço: ${resultado['preco']:.4f}
📊 Força: {forca_real:.1f}% ({forca_desc})
📏 Mínimo: {minimo_exigido:.1f}%
⏰ Horário: {resultado['timestamp'].strftime('%H:%M')} ({TIMEFRAME})

🚀 AÇÃO: {acao} AGORA!"""
            
            # Envia mensagem sem parse_mode (formatação normal)
            response = requests.post(self.url, json={
                'chat_id': self.chat_id,
                'text': mensagem
            }, timeout=10)
            
            sucesso = response.status_code == 200
            
            if sucesso:
                print(f"📱 Telegram enviado: {resultado['moeda']} - {tipo}")
            else:
                print(f"❌ Erro Telegram: {response.status_code}")
                
            return sucesso
            
        except Exception as e:
            print(f"❌ Erro ao enviar Telegram: {e}")
            return False