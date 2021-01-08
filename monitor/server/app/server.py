print("server.py: importing")

from webpie import WPApp, WPHandler
import sys, glob, json, time, os
from datetime import datetime

Version = "1.0"

class DataViewer(object):
    
    def __init__(self, path):
        self.Path = path
        
    def parse_filename(self, fn):
        # filename looks like this:
        #
        #   <rse>_%Y_%m_%d_%H_%M_<type>.<extension>
        #
        fn, ext = fn.rsplit(".",1)
        parts = fn.split("_")
        typ = parts[-1]
        timestamp_parts = parts[-6:-1]
        timestamp = "_".join(timestamp_parts)
        rse = "_".join(parts[:-6])
        return rse, timestamp, typ, ext
        
    def is_mounted(self):
        return os.path.isdir(self.Path)

    def status(self):
        if not os.path.isdir(self.Path):
            return "Data volume %s does not exist" % (self.Path,)
        return "OK"
        
    def list_rses(self):
        files = glob.glob(f"{self.Path}/*_stats.json")
        rses = set()
        for path in files:
            fn = path.rsplit("/",1)[-1]
            rse, timestamp, typ, ext = self.parse_filename(fn)
            rses.add(rse)
        return sorted(list(rses))
    
    def list_runs(self, rse):
        files = glob.glob(f"{self.Path}/{rse}_*_stats.json")
        runs = []
        for path in files:
            fn = path.split("/",1)[-1]
            rse, timestamp, typ, ext = self.parse_filename(fn)
            runs.append(timestamp)
        return sorted(runs)
        
    def last_run(self, rse):
        files = glob.glob(f"{self.Path}/{rse}_*_stats.json")
        last_file = sorted(files)[-1]
        fn = last_file.split("/",1)[-1]
        rse, timestamp, typ, ext = self.parse_filename(fn)
        return self.get_run(rse, timestamp)
        
    def get_data(self, rse, run, typ):
        ext = "json" if typ == "stats" else "list"
        path = f"{self.Path}/{rse}_{run}_{typ}.{ext}"
        try:
            f = open(path, "r")
        except:
            return None
        if typ == "stats":
            stats = json.loads(f.read())
            if "scanner" in stats:
                nfiles = ndirectories = 0
                for root_info in stats["scanner"]["roots"]:
                    nfiles += root_info["files"]
                    ndirectories += root_info["directories"]
                stats["scanner"]["total_files"] = nfiles
                stats["scanner"]["total_directories"] = ndirectories
            out = stats
        else:
            out = [l.strip() for l in f.readlines() if l.strip()]
        f.close()
        return out
                
    def get_run(self, rse, run):
        dark = self.get_data(rse, run, "D")
        missing = self.get_data(rse, run, "M")
        stats = self.get_data(rse, run, "stats")
        
        out = {
            "stats":stats,
            "dark":dark,
            "missing":missing
        }
        #print(out)
        return out

def display_file_list(lst):
    Indent = "    "
    last_items = []
    out = []
    for path in lst:
        items = [item for item in path.split("/") if item]
        n_common = 0
        for li, i in zip(items, last_items):
            if li == i:
                n_common += 1
            else:
                break
        tail = items[n_common:]
        indent = Indent * n_common
        for i, item in enumerate(tail):
            if i < len(tail)-1:
                item += "/"
            if not indent: item = "/" + item
            out.append(indent + item)
            indent += Indent
        last_items = items
    return out
    

class Handler(WPHandler):
    
    def index(self, request, relpath, **args):
        #
        # list available RSEs
        #
        rses = self.App.DataViewer.list_rses()
        infos = []
        for rse in rses:
            info = self.App.DataViewer.last_run(rse)
            errors = self.check_run(info)
            stats = info.get("stats")
            dark = info.get("dark")
            missing = info.get("missing")
            start_time = stats.get("dbdump_before",{}).get("start_time")
            ndark = len(dark) if dark is not None else "error"
            nmissing = len(missing) if missing is not None else "error"
            infos.append((rse, start_time, ndark, nmissing, len(errors)))
            
        #print(infos)
        return self.render_to_response("rses.html", infos=infos)
        
    def probe(self, request, relpath, **args):
        return self.App.DataViewer.status(), "text/plain"
        return "OK" if self.App.DataViewer.is_mounted() else ("Data directory unreachable", 500)

    def show_rse(self, request, relpath, rse=None, **args):
        runs = self.App.DataViewer.list_runs(rse)
        runs = sorted(runs, reverse=True)
        runs_with_stats = [(run, self.App.DataViewer.get_run(rse, run)["stats"]) for run in runs]
        #print("runs_with_stats:", runs_with_stats)
        
        infos = []
        for run in runs:
            info = self.App.DataViewer.get_run(rse, run)
            errors = self.check_run(info)
            stats = info.get("stats")
            dark = info.get("dark")
            missing = info.get("missing")
            start_time = stats.get("dbdump_before",{}).get("start_time")
            ndark = len(dark) if dark is not None else "error"
            nmissing = len(missing) if missing is not None else "error"
            infos.append((
                run, 
                {
                    "start_time":start_time, "ndark":ndark, "nmissing":nmissing,
                    "errors":len(errors)
                }
            ))
        #print(infos)
        return self.render_to_response("show_rse.html", rse=rse, runs=infos)

    def common_paths(self, lst, space="&nbsp;"):
        lst = sorted(lst)
        prev = []
        out = []
        for path in lst:
            parts = path.split("/")
            i = 0
            for j, (x, y) in enumerate(zip(prev, parts)):
                if x == y:
                    i = j
                else:
                    break
            head = "/".join(parts[:i+1])
            tail = "/".join(parts[i+1:])
            out.append(space*len(head)+"/"+tail)
            prev = parts
        return out
        
    def display_file_list(self, lst):
        Indent = "    "
        last_items = []
        out = []
        for path in lst:
            items = [item for item in path.split("/") if item]
            n_common = 0
            for li, i in zip(items, last_items):
                if li == i:
                    n_common += 1
                else:
                    break
            tail = items[n_common:]
            indent = Indent * n_common
            for i, item in enumerate(tail):
                if i < len(tail)-1:
                    item += "/"
                if not indent: item = "/" + item
                out.append(indent + item)
                indent += Indent
            last_items = items
        return out
    
    def check_run(self, run_info):
        errors = []
        if run_info.get("stats") is None:
            errors.append("run statistics are missing")
        else:
            stats = run_info["stats"]
            if not "scanner" in stats or stats["scanner"] is None:
                errors.append("Site scanner statistics missing")
            if not "dbdump_before" in stats or stats["dbdump_before"] is None:
                errors.append("DB dump before site scan statistics missing")
            if not "dbdump_after" in stats or stats["dbdump_after"] is None:
                errors.append("DB dump after site scan statistics missing")
            if not "cmp3" in stats or stats["cmp3"] is None:
                errors.append("Comparison statistics missing")
        if run_info.get("dark") is None:
            errors.append("Dark file list not found")
        if run_info.get("missing") is None:
            errors.append("Missing file list not found")
        return errors
        
    def dark(self, request, relpath, rse=None, run=None, **args):
        lst = self.App.DataViewer.get_data(rse, run, 'D')
        return [path+"\n" for path in lst], {
            "Content-Type":"text/plain",
            "Content-Disposition":"attachment"
        }
            
    def mssing(self, request, relpath, rse=None, run=None, **args):
        lst = self.App.DataViewer.get_data(rse, run, 'M')
        return [path+"\n" for path in lst], {
            "Content-Type":"text/plain",
            "Content-Disposition":"attachment"
        }
            
    def show_run(self, request, relpath, rse=None, run=None, **args):
        run_info = self.App.DataViewer.get_run(rse, run)
        errors = self.check_run(run_info)
        stats = run_info.get("stats", {}) 

        stats_parts = [(part, stats.get(part)) for part in ["dbdump_before", "scanner", "dbdump_after", "cmp3"]]
        scanner_roots = []
        if "scanner" in stats and "roots" in stats["scanner"]:
            scanner_roots = sorted(stats["scanner"]["roots"], key=lambda x:x["root"])
        
        dark = run_info.get("dark") or []
        missing = run_info.get("missing") or []
        nmissing = len(missing)
        ndark = len(dark)
        
        dark = dark[:1000]
        missing = missing[:1000]
        
        return self.render_to_response("show_run.html", 
            rse=rse, run=run,
            errors = errors,
            dbdump_before=stats.get("dbdump_before"),
            dbdump_after=stats.get("dbdump_after"),
            scanner=stats.get("scanner"),
            scanner_roots = scanner_roots,
            cmp3=stats.get("cmp3"),
            stats=stats,
            ndark = ndark, nmissing=nmissing,
            dark=self.display_file_list(dark),
            missing = self.display_file_list(missing),
            stats_parts=stats_parts
        )

def as_dt(t):
    # datetim in UTC
    dt = datetime.utcfromtimestamp(t)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
    
def as_json(d):
    return "\n"+json.dumps(d, indent=4)
    
def hms(t):
    if t < 100:
        return "%.2fs" % (t)
    
    t = int(t)
    s = t % 60
    t //= 60
    m = t % 60
    h = t // 60
    
    if h == 0:
        return f"{m}m{s}s"
    else:
        return f"{h}h{m}m"
        
def path_type(path):
    return "dir" if path.endswith("/") else "file"
    

class App(WPApp):

    Version = Version
    
    def __init__(self, handler, path, prefix):
        WPApp.__init__(self, handler, prefix=prefix)
        self.DataViewer = DataViewer(path)

    def init(self):
        import os
        home = os.path.dirname(__file__) or "."
        self.initJinjaEnvironment(tempdirs=[home], 
            filters={"hms":hms , "as_dt":as_dt, "as_json":as_json, "path_type":path_type}
            )
        
        
Usage = """
python server.py [-r <url prefix to remove>] <port> <data path>
"""

if __name__ == "__main__":
    import sys, getopt

    print("server.py: sys.argv:", sys.argv)

    opts, args = getopt.getopt(sys.argv[1:], "r:ld")
    opts = dict(opts)

    if not args:
        print (Usage)
        sys.exit(2) 
    
    port = int(args[0])
    path = args[1]
    
    prefix = opts.get("-r")
    logging="-l" in opts
    debug=sys.stdout if "-d" in opts else None

    print("Starting server on port %s with path %s" % (port, path))

    sys.stdout.flush()
    
    App(Handler, path, prefix).run_server(port, logging=logging, debug=debug)

        
        
        
        
        
