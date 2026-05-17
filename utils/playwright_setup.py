import subprocess
import sys
from playwright.sync_api import sync_playwright


def ensure_chromium_installed():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()

        return True

    except Exception as error:
        if getattr(sys, "frozen", False):
            print("\nNo se encontró Chromium dentro del ejecutable.")
            print("Debe generarse el .exe incluyendo los navegadores de Playwright.")
            print(f"\nDetalle: {error}")
            return False

        print("\nChromium de Playwright no está instalado.")
        print("Instalando Chromium automáticamente...")

        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True
            )
            return True

        except Exception as install_error:
            print("\nNo se pudo instalar Chromium automáticamente.")
            print("Ejecute manualmente:")
            print("python -m playwright install chromium")
            print(f"\nDetalle: {install_error}")
            return False