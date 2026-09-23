"""Start the built React UI and API on one local address."""
import argparse
import json
import socket
from pathlib import Path
from urllib.request import urlopen
import uvicorn


def main():
    parser = argparse.ArgumentParser(description='Start ADF Check locally.')
    parser.add_argument('--port', type=int, default=8000, help='Local port (default: 8000)')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    if not (Path(__file__).parent/'frontend'/'dist'/'index.html').exists():
        raise SystemExit('Build the React frontend first: cd frontend; npm.cmd install; npm.cmd run build')
    address = f'http://127.0.0.1:{args.port}'
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(('127.0.0.1', args.port))
        except OSError as exc:
            if exc.errno not in (48, 98, 10048) and getattr(exc, 'winerror', None) != 10048:
                raise SystemExit(f'Could not open {address}: {exc}')
            try:
                with urlopen(f'{address}/api/health', timeout=2) as response:
                    healthy = json.loads(response.read(8192)).get('status') == 'ok'
                with urlopen(address, timeout=2) as response:
                    is_adf = 'ADF Check' in response.read(8192).decode('utf-8', errors='replace')
                if healthy and is_adf:
                    print(f'ADF Check is already running. Open {address} in your browser.')
                    return
            except (OSError, ValueError):
                pass
            raise SystemExit(f'Port {args.port} is in use by another application. '
                             'Choose another port, for example: python run.py --port 8001')
        config = uvicorn.Config('api:app', host='127.0.0.1', port=args.port)
        uvicorn.Server(config).run(sockets=[listener])


if __name__ == '__main__':
    main()
