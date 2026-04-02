type Props = {
  title: string;
  subtitle?: string;
};

export function PageHeader({ title, subtitle }: Props) {
  return (
    <div className="mb-6">
      <h1 className="text-3xl font-bold tracking-tight text-white">{title}</h1>
      {subtitle ? (
        <p className="mt-2 text-sm text-slate-400">{subtitle}</p>
      ) : null}
    </div>
  );
}
