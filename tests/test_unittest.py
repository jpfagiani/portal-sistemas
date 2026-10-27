"""Porta de entrada para `python3 -m unittest discover -s tests -v`.

Os testes do portal estão em tests/test_modulos.py, escrito como script. Este arquivo o executa
e transforma o resultado em um teste do unittest, para quem usa o comando padrão."""
import os
import subprocess
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))


class TestePortal(unittest.TestCase):
    def test_modulos(self):
        r = subprocess.run([sys.executable, '-I', os.path.join(AQUI, 'test_modulos.py')],
                           capture_output=True, text=True, timeout=600)
        falhas = [l for l in r.stdout.splitlines() if l.startswith('FALHA')]
        self.assertEqual(r.returncode, 0, 'testes do portal falharam:\n' + '\n'.join(falhas) + r.stderr[-800:])
        self.assertGreater(r.stdout.count('\nOK '), 100)


if __name__ == '__main__':
    unittest.main()
