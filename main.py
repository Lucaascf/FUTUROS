# main.py - Versão FINAL corrigida para Fly.io
import threading
import time
import os
import traceback
from monitor import MonitorBinanceFutures
from config import get_config_summary
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime

class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suprimir logs HTTP para reduzir spam
        pass
    
    def do_GET(self):
        try:
            if self.path == '/health':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                try:
                    config = get_config_summary()
                    response = {
                        "status": "online",
                        "monitor": "running",
                        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S UTC'),
                        "config": config
                    }
                except Exception as e:
                    response = {
                        "status": "online", 
                        "monitor": "starting",
                        "error": str(e),
                        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S UTC')
                    }
                
                self.wfile.write(json.dumps(response, indent=2).encode())
            
            elif self.path == '/':
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Monitor Crypto Online</title>
                    <meta charset="utf-8">
                    <style>
                        body { font-family: Arial; margin: 40px; background: #0a0a0a; color: #fff; }
                        .container { max-width: 600px; margin: 0 auto; }
                        .status { background: #1a1a1a; padding: 20px; border-radius: 10px; margin: 20px 0; }
                        .online { color: #00ff88; }
                        a { color: #00aaff; text-decoration: none; }
                        a:hover { text-decoration: underline; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🚀 Monitor Crypto Online!</h1>
                        <div class="status">
                            <h2 class="online">✅ Sistema Funcionando</h2>
                            <p>📊 <a href="/health">Ver status detalhado (JSON)</a></p>
                            <p>🤖 Alertas via Telegram configurados</p>
                            <p>📈 Monitorando: BTC, ETH, ADA, SOL, AVAX, DOGE, XRP</p>
                            <p>⏱️ Timeframe: 4h | Estratégia: MA7 vs MA25+MA99</p>
                        </div>
                    </div>
                </body>
                </html>
                """
                self.wfile.write(html.encode())
            
            else:
                self.send_response(404)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'404 - Not Found')
                
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f'Error: {str(e)}'.encode())

def start_web_server():
    """Inicia servidor web para manter a aplicação viva"""
    # Detecta a porta automaticamente (Fly.io usa variável PORT)
    port = int(os.getenv('PORT', 8080))
    
    # Bind em todas as interfaces
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"🌐 Servidor web ativo na porta {port}")
    
    try:
        server.serve_forever()
    except Exception as e:
        print(f"❌ Erro no servidor web: {e}")

def main():
    """Função principal"""
    port = int(os.getenv('PORT', 8080))
    print(f"\n{'='*60}")
    print(f"🌐 INICIANDO APLICAÇÃO NO FLY.IO")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🖥️ PORT: {port}")
    print(f"{'='*60}\n")
    
    # Inicia servidor web em thread separada
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    
    # Aguarda servidor iniciar
    time.sleep(3)
    print("✅ Servidor web iniciado com sucesso")
    
    # Inicia o monitor com tratamento de erro robusto
    while True:
        try:
            print("🔄 Iniciando monitor de criptomoedas...")
            monitor = MonitorBinanceFutures()
            monitor.iniciar_monitoramento()
            
        except KeyboardInterrupt:
            print("\n🛑 Encerramento solicitado pelo usuário")
            break
            
        except Exception as e:
            print(f"\n❌ ERRO NO MONITOR")
            print(f"   🔍 Detalhes: {e}")
            print(f"   📝 Traceback:")
            traceback.print_exc()
            
            print("🔄 Reiniciando monitor em 60 segundos...")
            time.sleep(60)
            
        except:
            print("❌ Erro crítico desconhecido")
            print("🔄 Reiniciando monitor em 60 segundos...")
            time.sleep(60)

if __name__ == "__main__":
    main()