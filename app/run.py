"""Inicia API y worker; --dev agrega Vue/Vite con actualizacion automatica."""
import argparse
from contextlib import ExitStack
import os
import socket
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Event, Thread

import uvicorn


def stop_process(process):
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dev', action='store_true', help='Iniciar tambien Vue con Vite en el puerto 5173')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    node = shutil.which('node') if args.dev else None
    vite = root/'frontend'/'node_modules'/'vite'/'bin'/'vite.js'
    if args.dev and (not node or not vite.is_file()):
        print('Faltan Node o las dependencias de Vue. Ejecuta scripts/preparar.ps1.', flush=True)
        return 1
    if not args.dev and not (root / "frontend" / "dist" / "index.html").is_file():
        print("Falta compilar Vue. Ejecuta pnpm --dir frontend build antes de iniciar.", flush=True)
        return 1
    for port in ([8000, 5173] if args.dev else [8000]):
        try:
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', port))
        except OSError:
            print(f'El puerto {port} ya esta ocupado. Cierra el servidor anterior antes de iniciar ProInXML.', flush=True)
            return 1
    runtime = root / ".runtime"
    runtime.mkdir(exist_ok=True)
    server = uvicorn.Server(uvicorn.Config('app.main:app', host='127.0.0.1', port=8000))
    processes = []
    stopped = Event()
    failure = Event()
    with ExitStack() as stack:
        try:
            commands = [('worker', [sys.executable, '-m', 'app.worker'], root)]
            if args.dev:
                # Es el mismo ejecutable local que utiliza pnpm dev. Un proceso
                # Node directo permite detener Vite sin dejar un shell intermedio.
                commands.append(('vue', [node, str(vite), '--host', '127.0.0.1', '--port', '5173', '--strictPort'], root/'frontend'))
            for name, command, directory in commands:
                log = stack.enter_context((runtime/f'{name}.log').open('a', encoding='utf-8'))
                process = subprocess.Popen(command, cwd=directory, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                processes.append((name, process))

            def monitor():
                while not stopped.wait(.5):
                    for name, process in processes:
                        if process.poll() is not None:
                            print(f'{name} se detuvo. Revisa .runtime/{name}.log.', flush=True)
                            failure.set()
                            server.should_exit = True
                            return

            watcher = Thread(target=monitor, name='proinxml-monitor', daemon=True)
            watcher.start()
            print('ProInXML: http://127.0.0.1:5173' if args.dev else 'ProInXML: http://127.0.0.1:8000', flush=True)
            print('FastAPI: http://127.0.0.1:8000/docs | Ctrl+C detiene API, Vue y worker.', flush=True)
            try:
                server.run()
            except KeyboardInterrupt:
                print('ProInXML detenido.', flush=True)
        finally:
            stopped.set()
            for _, process in reversed(processes):
                stop_process(process)
    return 1 if failure.is_set() else 0


if __name__ == "__main__":
    raise SystemExit(main())
