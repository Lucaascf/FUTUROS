# main.py - Versão corrigida para Fly.io
import threading
import time
import os
from monitor import MonitorBinanceFutures
from config import get_config_summary
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            try:
                config = get_config_summary()
                response = {
                    "status": "online",
                    "monitor": "running",
                    "config": config
                }
            except Exception as e:
                response = {
                    "status": "online", 
                    "monitor": "starting",
                    "error": str(e)
                }
            
            self.wfile.write(json.dumps(response, indent=2).encode())
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = """
            <h1>🚀 Monitor Crypto Online!</h1>
            <p>✅ Sistema funcionando</p>
            <p>📊 <a href="/health">Ver status detalhado</a></p>
            """
            self.wfile.write(html.encode())

def start_web_server():
    """Inicia servidor web para manter a aplicação viva"""
    port = int(os.getenv('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"🌐 Servidor web iniciado na porta {port}")
    server.serve_forever()

def main():
    """Função principal"""
    print("🚀 Iniciando aplicação no Fly.io...")
    
    # Inicia servidor web em thread separada
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    
    # Aguarda um pouco para o servidor iniciar
    time.sleep(2)
    
    # Inicia o monitor
    try:
        monitor = MonitorBinanceFutures()
        monitor.iniciar_monitoramento()
    except Exception as e:
        print(f"❌ Erro no monitor: {e}")
        # Mantém o servidor web vivo mesmo se o monitor falhar
        while True:
            time.sleep(60)

if __name__ == "__main__":
    main()