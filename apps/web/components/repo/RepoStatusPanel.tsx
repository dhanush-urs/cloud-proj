import { Card } from "@/components/common/Card";
import { Repository } from "@/lib/types";
import { Activity, CheckCircle2, Clock, Terminal, ShieldAlert } from "lucide-react";

export function RepoStatusPanel({ repo }: { repo: Repository }) {
  const isSyncing = ["indexing", "parsing", "embedding", "pending", "queued", "running"].includes(repo.status || "");
  const isError = repo.status === "failed";
  const isReady = ["ready", "success", "parsed", "indexed", "embedded"].includes(repo.status || "");

  const sanitizeFramework = (val?: string | null) => {
    if (!val) return "";
    return val.replace(/[{}[\]"']/g, "").split(",").map(s => s.trim()).filter(Boolean).join(", ");
  };

  return (
    <Card className="p-6 border-slate-800 bg-slate-900/40 backdrop-blur-sm">
      <div className="flex flex-col md:flex-row items-start gap-6">
        <div className={`p-4 rounded-2xl ${
          isSyncing ? "bg-amber-500/10 text-amber-500 animate-pulse" : 
          isError ? "bg-red-500/10 text-red-500" :
          "bg-emerald-500/10 text-emerald-500"
        }`}>
          {isSyncing ? <Activity size={32} /> : 
           isError ? <ShieldAlert size={32} /> :
           <CheckCircle2 size={32} />}
        </div>
        
        <div className="flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="text-xl font-bold text-white tracking-tight">Intelligence System Status</h3>
            <span className={`px-2.5 py-0.5 rounded text-[10px] font-black uppercase tracking-widest border ${
              isSyncing ? "bg-amber-500/20 text-amber-400 border-amber-500/30" : 
              isError ? "bg-red-500/20 text-red-400 border-red-500/30" :
              "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
            }`}>
              {repo.status || "UNKNOWN"}
            </span>
          </div>
          
          <p className="text-sm text-slate-400 leading-relaxed max-w-2xl">
          {isSyncing 
              ? "The repository is currently being processed. Our ingestion pipeline is building a semantic graph of your codebase."
              : isError
              ? "An error occurred during the last synchronization attempt. Please check the logs below or retry the operation."
              : repo.status === "embedded"
              ? "Repository is fully embedded and ready for semantic search and Ask Repo queries."
              : repo.status === "indexed"
              ? "Repository files are indexed. Click Embed Repository to enable semantic search."
              : repo.status === "parsed"
              ? "Repository is parsed and ready for embedding. Click Embed Repository to enable AI Q&A."
              : "Intelligence system is fully operational. All code symbols, dependencies, and file structures are indexed."}
          </p>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 pt-4">
            <div className="flex items-center gap-3 p-3 rounded-xl bg-slate-950/40 border border-slate-800/50">
              <Clock size={16} className="text-slate-500" />
              <div>
                <p className="text-[10px] uppercase text-slate-500 font-bold tracking-tight">Registry Date</p>
                <p className="text-sm text-slate-300 font-medium">{repo.created_at ? new Date(repo.created_at).toLocaleDateString() : 'N/A'}</p>
              </div>
            </div>
            
            <div className="flex items-center gap-3 p-3 rounded-xl bg-slate-950/40 border border-slate-800/50">
              <Terminal size={16} className="text-slate-500" />
              <div>
                <p className="text-[10px] uppercase text-slate-500 font-bold tracking-tight">Primary Tech</p>
                <p className="text-sm text-slate-300 font-medium">
                  {repo.primary_language || 'Generic'} {repo.framework ? `(${sanitizeFramework(repo.framework)})` : ''}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
