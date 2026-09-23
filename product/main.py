"""Windows desktop entry. --headless supports automated integration checks."""
import argparse
import ctypes
import json
import logging
import os
import sys
import threading
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--headless',action='store_true')
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--data-dir')
    parser.add_argument('--smoke-test',action='store_true')
    args=parser.parse_args()
    data=Path(args.data_dir or Path(os.getenv('LOCALAPPDATA',str(Path.home())))/'YingInWork')
    data.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=data/'app.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',encoding='utf-8')
    if sys.stdout is None: sys.stdout=open(os.devnull,'w')
    if sys.stderr is None: sys.stderr=open(data/'errors.log','a',encoding='utf-8')
    # Session mutex prevents two product windows from competing for the camera.
    mutex=None
    if not args.headless and not args.smoke_test:
        ctypes.windll.kernel32.CreateMutexW.restype=ctypes.c_void_p
        mutex=ctypes.windll.kernel32.CreateMutexW(None,False,'Local\\YingInWorkDesktop')
        if ctypes.windll.kernel32.GetLastError()==183:
            ctypes.windll.user32.MessageBoxW(0,'萤 In Work 已在运行，请从任务栏或托盘打开。','萤 In Work',0)
            return
    from service import ProductService
    from server import create_app
    from waitress import create_server
    service=ProductService(ROOT,data)
    app=create_app(service)
    server=create_server(app,host='127.0.0.1',port=args.port,threads=8)
    port=server.effective_port
    url=f'http://127.0.0.1:{port}'
    if args.headless:
        (data/'runtime.json').write_text(json.dumps({'url':url,'token':app.config['TOKEN']}),'utf-8')
        print(url,flush=True)
        try: server.run()
        finally: service.close();server.close()
        return
    threading.Thread(target=server.run,daemon=True).start()
    import webview
    from PIL import Image
    import pystray
    floating = [None]
    fullscreen_lock = threading.Lock()
    fullscreen = [False]
    class Desktop:
        def minimize(self): window.minimize()
        def hide(self): window.hide()
        def quit(self): window.destroy()
        def set_fullscreen(self, enabled):
            with fullscreen_lock:
                if bool(enabled) != fullscreen[0]:
                    window.toggle_fullscreen()
                    fullscreen[0] = bool(enabled)
            return {'fullscreen': fullscreen[0]}
        def show_float(self):
            service.update_settings({'floating_window': True})
            if floating[0]:
                from System import Action
                window.native.Invoke(Action(floating[0].show))
        def export_records(self):
            paths=window.create_file_dialog(webview.SAVE_DIALOG,save_filename='萤InWork-个人记录.json',file_types=('JSON (*.json)',))
            if not paths: return {'saved':False}
            target=Path(paths if isinstance(paths,str) else paths[0])
            target.write_text(json.dumps(service.history(),ensure_ascii=False,indent=2),'utf-8')
            return {'saved':True,'name':target.name}
    window=webview.create_window('萤 In Work · 你的工作情绪搭子',url,js_api=Desktop(),width=1420,height=900,min_size=(1080,720),background_color='#F8F7F3',text_select=True,hidden=args.smoke_test)
    def show(*_): window.show();window.restore()
    def pause(*_): threading.Thread(target=service.stop_camera,daemon=True).start()
    tray=pystray.Icon('YingInWork',Image.open(ROOT/'frontend/assets/ying.png'),'萤 In Work',pystray.Menu(
        pystray.MenuItem('打开萤 In Work',show,default=True),pystray.MenuItem('暂停陪伴',pause),pystray.MenuItem('退出',lambda *_:window.destroy())))
    def closed():
        tray.stop()
        service.close()
        server.close()
    window.events.closed += closed
    def closing():
        if floating[0]:
            from System import Action
            try: window.native.Invoke(Action(floating[0].close))
            except Exception: logging.exception('Floating window cleanup failed')
    window.events.closing += closing
    threading.Thread(target=tray.run,daemon=True).start()
    def desktop_notifications():
        last_id=0
        while not service.stop_event.wait(1):
            for item in list(service.notifications):
                if item['id']<=last_id: continue
                last_id=item['id']
                if service.settings['dnd']: continue
                try: tray.notify(item['label'],'萤 In Work · 休息一下')
                except Exception: logging.info('System notification unavailable')
    threading.Thread(target=desktop_notifications,daemon=True).start()
    def ready():
        import time
        from System import Action
        from floating_companion import FloatingCompanion
        window.events.loaded.wait(20)
        def create_float():
            floating[0] = FloatingCompanion(window, service, ROOT)
        try:
            window.native.Invoke(Action(create_float))
        except Exception:
            logging.exception('Floating companion initialization failed')
        if not args.smoke_test:
            if service.settings['auto_start']:
                try: service.start_camera()
                except Exception as exc:
                    service.camera.error = str(exc)
                    service.notify('camera', str(exc))
            return
        time.sleep(2)
        try:
            result=window.evaluate_js('({title:document.title,ready:!!window.inworkReady,buttons:document.querySelectorAll("button").length,errors:window.uiErrors||[]})')
            result['floating_created'] = floating[0] is not None
            if floating[0]:
                checks = []
                window.native.Invoke(Action(lambda: checks.append(floating[0].self_test())))
                result['floating_checks'] = checks[0]
            (data/'desktop-smoke.json').write_text(json.dumps(result,ensure_ascii=False),'utf-8')
        finally: window.destroy()
    webview.start(ready,gui='edgechromium',private_mode=False,storage_path=str(data/'webview'),icon=str(ROOT/'assets/ying.ico'))


if __name__=='__main__':
    try: main()
    except Exception as exc:
        logging.exception('Startup failed')
        if '--headless' in sys.argv: raise
        ctypes.windll.user32.MessageBoxW(0,f'启动失败：{exc}\n请检查同目录文件是否完整，以及 Microsoft Edge WebView2 是否已安装。','萤 In Work',16)
