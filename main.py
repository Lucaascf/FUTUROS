# main.py - Versão para Fly.io com servidor web
import threading
import time
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
            
            config = get_config_summary()
            response = {
                "status": "online",
                "monitor": "running",
                "config": config
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
    server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
    print("🌐 Servidor web iniciado na porta 8080")
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
    monitor = MonitorBinanceFutures()
    monitor.iniciar_monitoramento()

if __name__ == "__main__":
    main()