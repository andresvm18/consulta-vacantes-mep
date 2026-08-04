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
            print("Playwright Chromium no está instalado y no se puede instalar automáticamente desde un ejecutable empaquetado.")
            print("El ejecutable debe construirse con los navegadores de Playwright incluidos.")
            print(f"Detalles: {error}")
            return False

        print("Playwright Chromium no está instalado. Instalándolo automáticamente...")

        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True
            )
            return True

        except Exception:
            print("Error al instalar Playwright Chromium automáticamente.")
            print("Por favor, instálalo manualmente:")
            print("python -m playwright install chromium")
            return False
