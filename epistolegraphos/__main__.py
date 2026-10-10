"""python -m epistolegraphos [--puerto 8080] [--sin-navegador]"""

import argparse
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()  # letters are rendered in worker processes
    parser = argparse.ArgumentParser(prog="epistolegraphos")
    parser.add_argument("--puerto", type=int, default=8080)
    parser.add_argument("--sin-navegador", action="store_true")
    args = parser.parse_args()

    from epistolegraphos.interfaz import iniciar

    iniciar(args.puerto, not args.sin_navegador)
