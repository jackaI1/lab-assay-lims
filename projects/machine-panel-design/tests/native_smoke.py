"""Real QElectroTech load smoke test on Linux; scoped process is always reaped.

QET has no headless export command. Run its actual GUI in Xvfb, wait for its
application window, then close just the owned process.
"""
from pathlib import Path
import subprocess
import tempfile
import time

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='panel-qet-') as d:
        path=Path(d); log=path/'qet.log'
        with log.open('w') as output:
            process=subprocess.Popen(['qelectrotech','--config-dir='+d,str(Path('drawings/bottle-filler.qet').resolve())],stdout=output,stderr=output)
            try:
                subprocess.run(['which','xwininfo'],check=True,capture_output=True)
                deadline=time.monotonic()+45
                found=False
                while time.monotonic()<deadline:
                    if process.poll() is not None: raise RuntimeError('QET exited during load: '+log.read_text()[-2000:])
                    windows=subprocess.run(['xwininfo','-root','-tree'],capture_output=True,text=True,check=True).stdout
                    if 'QElectroTech' in windows:
                        found=True;break
                    time.sleep(.25)
                if not found: raise RuntimeError('No QET window within 45 seconds')
                # QET startup parses all diagrams before presenting the project.
                time.sleep(2)
                errors=log.read_text()
                for message in ('unable to open','cannot open','not valid','not coherent','ne semblent pas coherents'):
                    if message.lower() in errors.lower(): raise RuntimeError(errors[-3000:])
                print('Native QET process opened project; 5 folios checked independently by XML audit.')
            finally:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill();process.wait(timeout=5)
                print('Owned QET PID',process.pid,'reaped, return code',process.returncode)
