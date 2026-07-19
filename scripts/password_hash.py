# generar_password_hash.py
# Corre esto UNA VEZ para elegir la contraseña de acceso a AtypicalTick.
# Uso:
#   python scripts/generar_password_hash.py
#
# El resultado va en tu .env como APP_PASSWORD_HASH. La contraseña
# en sí misma NO se guarda en ningún lado, solo su hash.

import getpass
import hashlib
import os
import sys


def main():
    password = getpass.getpass("Elige tu contraseña de acceso a AtypicalTick: ")
    confirmacion = getpass.getpass("Confírmala: ")

    if password != confirmacion:
        print("\nLas contraseñas no coinciden. Nada se guardó.")
        sys.exit(1)

    if len(password) < 8:
        print("\nUsa al menos 8 caracteres.")
        sys.exit(1)

    salt = os.urandom(16)
    hash_ = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)

    print("\nAgrega esta línea a tu archivo .env:\n")
    print(f"APP_PASSWORD_HASH={salt.hex()}${hash_.hex()}")
    print("\n(Si cambias de contraseña, vuelve a correr este script y reemplaza el valor.)")


if __name__ == "__main__":
    main()