"""Read-only, bounded local desktop discovery.

This module deliberately exposes metadata, not arbitrary shell access. File
contents, process arguments, hidden folders, credentials and global input are
outside this first desktop capability boundary.
"""
from __future__ import annotations

import csv
import io
import os
from pathlib import Path
import platform
import subprocess
import time


class DesktopObserver:
    def __init__(self, roots=None, *, clock=time.monotonic):
        home=Path.home()
        self.roots=[Path(item).resolve() for item in (roots or
            [home/'Desktop',home/'Documents',home/'Downloads']) if Path(item).exists()]
        self.clock=clock

    def find_files(self, query, *, limit=40, max_seconds=3):
        query=str(query or '').strip().casefold()
        if len(query)<2:
            raise ValueError('Bitte mindestens zwei Zeichen des Datei- oder Ordnernamens angeben.')
        started=self.clock();matches=[];scanned=0
        for root in self.roots:
            for folder,dirs,files in os.walk(root,followlinks=False):
                dirs[:]=[name for name in dirs if not name.startswith('.') and name not in
                         {'node_modules','__pycache__','.git','.venv','Library'}]
                for name in [*dirs,*files]:
                    scanned+=1
                    if query in name.casefold():
                        path=Path(folder,name)
                        try:
                            stat=path.stat()
                        except OSError:
                            continue
                        matches.append({'name':name,'path':str(path.resolve()),
                            'kind':'folder' if path.is_dir() else 'file',
                            'size':None if path.is_dir() else stat.st_size,
                            'modified_at':int(stat.st_mtime)})
                        if len(matches)>=limit:
                            return {'query':query,'matches':matches,'scanned':scanned,'truncated':True}
                if self.clock()-started>=max_seconds:
                    return {'query':query,'matches':matches,'scanned':scanned,'truncated':True}
        return {'query':query,'matches':matches,'scanned':scanned,'truncated':False}

    @staticmethod
    def _unix_processes(text):
        result=[]
        for line in text.splitlines():
            fields=line.strip().split(None,4)
            if len(fields)!=5:
                continue
            try:
                pid,cpu,memory=int(fields[0]),float(fields[1]),float(fields[2])
            except ValueError:
                continue
            result.append({'pid':pid,'cpu_percent':cpu,'memory_percent':memory,
                           'elapsed':fields[3],'name':Path(fields[4]).name})
        return result

    def processes(self, query='', *, limit=50):
        query=str(query or '').strip().casefold()
        if os.name=='nt':
            run=subprocess.run(['tasklist','/FO','CSV','/NH'],capture_output=True,text=True,
                               timeout=5,check=True)
            rows=csv.reader(io.StringIO(run.stdout));items=[]
            for row in rows:
                if len(row)>=2 and row[1].isdigit():
                    items.append({'pid':int(row[1]),'cpu_percent':None,'memory_percent':None,
                                  'elapsed':None,'name':row[0]})
        else:
            run=subprocess.run(['ps','-axo','pid=,pcpu=,pmem=,etime=,comm='],capture_output=True,
                               text=True,timeout=5,check=True)
            items=self._unix_processes(run.stdout)
        if query:
            items=[item for item in items if query in item['name'].casefold()]
        items.sort(key=lambda item: (-(item['cpu_percent'] or 0),item['name'].casefold(),item['pid']))
        return {'query':query,'processes':items[:limit],'total_matches':len(items),
                'arguments_included':False}

    def apps(self, query='', *, limit=80):
        query=str(query or '').strip().casefold();items=[]
        system=platform.system()
        if system=='Darwin':
            roots=[Path('/Applications'),Path.home()/'Applications']
            suffix='.app'
        elif system=='Windows':
            roots=[Path(os.environ.get('ProgramData',''))/'Microsoft/Windows/Start Menu/Programs',
                   Path(os.environ.get('APPDATA',''))/'Microsoft/Windows/Start Menu/Programs']
            suffix='.lnk'
        else:
            roots=[Path('/usr/share/applications'),Path.home()/'.local/share/applications']
            suffix='.desktop'
        for root in roots:
            if not root.exists(): continue
            for path in root.rglob('*'+suffix):
                name=path.name[:-len(suffix)]
                if not query or query in name.casefold():
                    items.append({'name':name,'path':str(path.resolve())})
        unique={item['path']:item for item in items}
        ordered=sorted(unique.values(),key=lambda item:item['name'].casefold())
        return {'query':query,'apps':ordered[:limit],'total_matches':len(ordered)}

    def foreground(self):
        system=platform.system()
        if system=='Darwin':
            run=subprocess.run(['osascript','-e','tell application "System Events" to get name of first application process whose frontmost is true'],
                               capture_output=True,text=True,timeout=5,check=True)
            name=run.stdout.strip()
        elif system=='Linux':
            run=subprocess.run(['xdotool','getactivewindow','getwindowname'],capture_output=True,
                               text=True,timeout=5,check=True)
            name=run.stdout.strip()
        else:
            name='Auf Windows ist die Vordergrund-App in dieser Vorschau noch nicht verfügbar.'
        return {'foreground_app':name,'observation':'metadata_only'}

    def run(self, operation, query=''):
        if operation=='find_files': return self.find_files(query)
        if operation=='list_processes': return self.processes(query)
        if operation=='list_apps': return self.apps(query)
        if operation=='foreground_app': return self.foreground()
        raise ValueError('Diese Desktop-Aktion ist noch nicht als sicherer Lesezugriff verfügbar.')
