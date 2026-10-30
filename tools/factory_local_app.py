#!/usr/bin/env python3
"""Loopback-only companion; run on the user's PC for local folder delivery.

No cloud hosting, credentials, generation/upload route or arbitrary command.
Closing a browser tab does not stop the worker process.
"""
import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import shutil
import threading
import platform
import sys
from urllib.parse import parse_qs
import factory_orchestrator as factory
import youtube_factory as youtube


def doctor():
    return {'requirements': {p: shutil.which(p) for p in ('node','ffmpeg','ffprobe')},
            'platform':platform.system(),'pythonVersion':platform.python_version(),'pythonExecutable':sys.executable,
            'clipFarmingCheckout': (factory.REPO.parent/'clipfarming/tools/local_shorts.py').is_file(),
            'userPcFolderTested': False, 'policy': factory.POLICY}


def create_server(root, port=8765):
    root = Path(root).resolve(); factory.init(root); (root/'inbox').mkdir(exist_ok=True)
    token = secrets.token_urlsafe(32); worker = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass

        def safe_host(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def respond(self, status, text):
            self.send_response(status); self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Frame-Options','DENY'); self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers(); self.wfile.write(text.encode())

        def field(self, body, name):
            if len(body.get(name, [])) != 1: raise ValueError('Falta el campo '+name)
            return body[name][0]

        def stash(self, value):
            path = factory.owned(root,'inbox','pasted',factory.fingerprint(value)+'.json'); path.parent.mkdir(exist_ok=True)
            if not path.exists(): factory.render.atomic_json(path,value)
            return path

        def do_GET(self):
            if not self.safe_host(): return self.respond(403,'Host no permitido')
            if self.path != '/': return self.respond(404,'No existe')
            with factory.connect(root) as db:
                reports = [dict(r) for r in db.execute('SELECT id FROM idea_reports ORDER BY rowid DESC')]
                jobs = [dict(r) for r in db.execute('SELECT id,channel,choice,state,error FROM productions ORDER BY rowid DESC')]
                progress = {r['job_id']:r['n'] for r in db.execute('SELECT job_id,count(*) AS n FROM production_stages GROUP BY job_id')}
            options = ''.join(f'<option>{escape(r["id"])}</option>' for r in reports)
            choices = ''.join(f'<option value="{escape(r["id"])}">Vídeo {r["choice"]} · {escape(r["channel"])}</option>' for r in jobs)
            csrf = f'<input type="hidden" name="csrf" value="{token}">'
            def form(action,title,fields,button):
                return f'<section><h2>{title}</h2><form method="post" action="/{action}">{csrf}{fields}<button>{button}</button></form></section>'
            rows = ''.join(f'<tr><td>Vídeo {r["choice"]}</td><td>{escape(r["channel"])}</td><td>{escape(r["state"])} · {progress.get(r["id"],0)}/6</td><td>{escape(r["error"] or "")}</td></tr>' for r in jobs)
            publishing=youtube.dashboard(root)
            batch_options=''.join(f'<option value="{escape(b["id"])}">{escape(b["id"])} · {escape(b["origin"])}</option>' for b in publishing['batches'])
            channel_rows=''.join(f'<tr><td>{escape(c["role"])}</td><td>{escape(c["title"])}</td><td>{escape(c["channel_id"])}</td><td>{escape(c["origin"])}</td></tr>' for c in publishing['channels'])
            upload_rows=''.join(f'<tr><td>{escape(i["file"])}</td><td>{escape(i["channel_id"])}</td><td>{escape(i["origin"])} · {escape(i["state"])}</td><td>{escape(youtube.utc(i["publish_at"]) if i["publish_at"] else "Privado sin fecha")}</td><td>{escape(i["error"] or "")}</td></tr>' for i in publishing['items'])
            page = '''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Fábrica local</title>
<style>body{font:16px system-ui;background:#f5f4ef;color:#21322c;margin:32px auto;max-width:1050px;padding:0 20px}h1{font-size:32px}section{background:white;padding:20px;border:1px solid #d7ddd7;border-radius:10px;margin:16px 0}h2{font-size:20px}label{display:block;margin:12px 0}textarea,input,select{display:block;box-sizing:border-box;width:100%;padding:9px;font:inherit}textarea{min-height:100px}button{background:#245c45;color:white;border:0;padding:11px 20px;border-radius:6px;cursor:pointer}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:9px;border-bottom:1px solid #ddd}p{line-height:1.5}.badge{background:#dfeadd;padding:10px;border-radius:6px}</style>
<h1>Fábrica de vídeos local</h1><p class="badge">Sin servicios de pago · generación bloqueada · resultados para revisar</p>
<p>Guarda dentro de la carpeta elegida al iniciar. No sube ni publica vídeos. Puedes cerrar la pestaña mientras procesa; conserva abierta la aplicación local.</p>'''
            page += form('report','1. Informe de ideas','<label>Informe JSON<textarea name="report" required></textarea></label>','Guardar informe')
            page += form('select','2. Elegir un vídeo',f'<label>Informe<select name="report_id" required>{options}</select></label><label>Tu elección<input name="choice" value="Haz el vídeo 3" required></label>','Preparar vídeo')
            page += form('script','3. Guion preparado',f'<label>Vídeo<select name="id" required>{choices}</select></label><label>Guion JSON<textarea name="script" required></textarea></label><label>Título, descripción y etiquetas en JSON<textarea name="metadata" required></textarea></label>','Incorporar guion')
            page += form('media','4. Material ya existente',f'<label>Vídeo<select name="id" required>{choices}</select></label><label>Manifiesto dentro de inbox/<input name="ready" placeholder="video-3/assets.ready.json" required></label><p>No genera imágenes ni voces. Conserva la asociación de cada archivo con su escena.</p>','Incorporar archivos')
            page += form('work','5. Procesar cola','<p>Montaje, Shorts, comprobaciones y carpeta final. Si falta contenido, queda en espera sin gastar cuota.</p>','Procesar siguiente vídeo')
            page += f'<section><h2>Estado</h2><table aria-label="Producciones"><tr><th>Elección</th><th>Canal</th><th>Estado</th><th>Detalle</th></tr>{rows}</table><p><a href="/">Actualizar estado</a></p></section>'
            page += f'<section><h2>Canales de YouTube</h2><p>La conexión oficial se completa personalmente en este ordenador mediante OAuth. No pegues contraseñas ni tokens.</p><table aria-label="Canales"><tr><th>Perfil</th><th>Nombre confirmado</th><th>ID exacto</th><th>Evidencia</th></tr>{channel_rows}</table></section>'
            page += form('youtube-plan','6. Revisar entrega para YouTube',f'<label>Vídeo<select name="id" required>{choices}</select></label><label>Revisión y calendario JSON<textarea name="schedule" required></textarea></label><p>Crea un plan local con canal, archivos, visibilidad y fechas. No autoriza ni ejecuta subidas.</p>','Preparar plan sin subir')
            page += f'<section><h2>Calendario de entregas</h2><table aria-label="Calendario YouTube"><tr><th>Archivo</th><th>Canal</th><th>Estado</th><th>Fecha UTC</th><th>Error</th></tr>{upload_rows}</table><p>Los resultados de simulación no prueban una subida real.</p></section>'
            page += form('cleanup-preview','7. Simular limpieza',f'<label>Entrega<select name="batch" required>{batch_options}</select></label><p>Guarda la lista exacta, hashes, comprobaciones y bytes potenciales en cleanup-simulations/. Borrado desactivado. Espacio liberado: 0 bytes.</p>','Calcular sin borrar')
            page += '</html>'
            self.respond(200,page)

        def do_POST(self):
            if not self.safe_host(): return self.respond(403,'Host no permitido')
            if self.headers.get('Origin') not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
                return self.respond(403,'Origen no permitido')
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 6*1024*1024: raise ValueError('Formulario demasiado grande')
                if self.headers.get('Content-Type','').split(';')[0] != 'application/x-www-form-urlencoded': raise ValueError('Formato no permitido')
                body = parse_qs(self.rfile.read(length).decode(),keep_blank_values=True)
                if not secrets.compare_digest(self.field(body,'csrf'),token): return self.respond(403,'Formulario no autorizado')
                if self.path == '/report': factory.import_report(root,self.stash(json.loads(self.field(body,'report'))))
                elif self.path == '/select': factory.select(root,self.field(body,'report_id'),self.field(body,'choice'))
                elif self.path == '/script': factory.attach_script(root,self.field(body,'id'),self.stash(json.loads(self.field(body,'script'))),self.stash(json.loads(self.field(body,'metadata'))))
                elif self.path == '/media':
                    relative = Path(self.field(body,'ready'))
                    if relative.is_absolute() or '..' in relative.parts: raise ValueError('Usa una ruta dentro de inbox/')
                    factory.attach_media(root,self.field(body,'id'),factory.owned(root/'inbox',relative))
                elif self.path == '/work':
                    if not worker.acquire(blocking=False): raise ValueError('Ya hay un vídeo en proceso')
                    def run():
                        try: factory.scan_inbox(root); factory.run_once(root)
                        finally: worker.release()
                    threading.Thread(target=run,daemon=False).start()
                elif self.path == '/youtube-plan': youtube.prepare(root,self.field(body,'id'),json.loads(self.field(body,'schedule')))
                elif self.path == '/cleanup-preview':
                    report=youtube.cleanup_simulation(root,self.field(body,'batch'))
                    rows=''.join(f'<tr><td>{escape(a["path"])}</td><td>{a["bytes"]:,}</td><td><code>{a["sha256"]}</code></td></tr>' for a in report['files'])
                    blocks=''.join(f'<li>{escape(b)}</li>' for b in report['blockers'])
                    self.respond(200,f'<!doctype html><html lang="es"><meta charset="utf-8"><title>Simulación de limpieza</title><h1>Simulación: no se ha borrado ningún archivo</h1><p>Espacio potencial: {report["potentialBytes"]:,} bytes. Espacio liberado: 0 bytes.</p><ul>{blocks}</ul><table><tr><th>Archivo generado</th><th>Bytes</th><th>SHA-256</th></tr>{rows}</table><p>Se conservan originales, guiones, prompts, metadatos y registros.</p><a href="/">Volver</a></html>')
                    return
                else: return self.respond(404,'No existe')
                self.send_response(303); self.send_header('Location','/'); self.end_headers()
            except (ValueError,OSError,KeyError) as error:
                self.respond(400,f'<p>{escape(str(error))}</p><a href="/">Volver</a>')
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root');p.add_argument('--port',type=int,default=8765);p.add_argument('--doctor',action='store_true');a=p.parse_args()
    if a.doctor: print(json.dumps(doctor(),ensure_ascii=False,indent=2))
    else:
        if not a.root: p.error('Choose a new dedicated folder using --root')
        server=create_server(a.root,a.port);print(f'Fábrica local: http://127.0.0.1:{server.server_port}/',flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: server.server_close()
