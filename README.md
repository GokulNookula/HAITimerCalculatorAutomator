Paste this entire content into your `README.md`:

# HAI Timer Calculator Automator

This project scrapes Handshake AI task/payment data and creates a CSV plus an Excel earnings tracker.

## What the PyInstaller build gives users

The PyInstaller build bundles the Python runtime and Python packages into one executable for the operating system you build on.

You must build once on each target OS:

* Windows creates `dist/HAITimerCalculatorAutomator.exe`
* macOS creates `dist/HAITimerCalculatorAutomator`
* Linux creates `dist/HAITimerCalculatorAutomator`

PyInstaller does not cross-compile, so a Windows computer cannot create the macOS/Linux binary directly.

## End-user requirements

End users do **not** need to install Python packages when using the built executable.

They still need:

1. Google Chrome installed.
2. Internet access the first time ChromeDriver/Selenium Manager resolves the browser driver.
3. Permission to open automated Chrome windows.

## Build on Windows

Open PowerShell or Command Prompt inside the project folder and run:

```bat
build-windows.bat
```

The script automatically creates a local `.venv-build` environment, installs all Python dependencies from `requirements.txt`, and runs PyInstaller.

The output will be:

```text
dist\HAITimerCalculatorAutomator.exe
```

## Build on macOS or Linux

Open Terminal inside the project folder and run:

```bash
chmod +x build-macos-linux.sh
./build-macos-linux.sh
```

The script automatically creates a local `.venv-build` environment, installs all Python dependencies from `requirements.txt`, and runs PyInstaller.

The output will be:

```text
dist/HAITimerCalculatorAutomator
```

## Run from source during development

The source code is inside the `Code/` folder, so run the app as a module from the main project folder.

On Windows:

```bat
python -m pip install -r requirements.txt
python -m Code.main
```

On macOS or Linux:

```bash
python3 -m pip install -r requirements.txt
python3 -m Code.main
```

If your system uses `python` instead of `python3`, use `python` for the macOS/Linux commands.

## Notes

* The app is a console program because it asks questions with `input()`.
* The default output folder is `Output`.
* If users double-click the Windows executable, the console window stays open at the end so they can read errors or success messages.
* If macOS blocks the executable, right-click it and choose **Open**, or run it from Terminal.
* The executable still requires Google Chrome because the scraper opens Chrome with Selenium.
* The executable should be built separately on Windows, macOS, and Linux.
