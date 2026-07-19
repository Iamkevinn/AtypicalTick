# generar_encryption_key.py
# Corre esto UNA VEZ para generar la clave que cifra en reposo el
# access_token / refresh_token de TickTick guardados en SQLite.
# Uso:
#   python scripts/generar_encryption_key.py
#
# El resultado va en tu .env como TOKEN_ENCRYPTION_KEY.
#
# IMPORTANTE: si ya tienes un token guardado sin cifrar y agregas
# esta clave después, el próximo guardar_token() (ej. al reautenticar
# con TickTick) lo guardará cifrado. No hace falta migrar nada a mano;
# solo verifica que TOKEN_ENCRYPTION_KEY no cambie una vez que empieces
# a usarla, o los tokens ya cifrados quedarán ilegibles.

from cryptography.fernet import Fernet

if __name__ == "__main__":
    print("\nAgrega esta línea a tu archivo .env:\n")
    print(f"TOKEN_ENCRYPTION_KEY={Fernet.generate_key().decode()}")