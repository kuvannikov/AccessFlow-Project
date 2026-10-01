export default function Logo({ light = false }: { light?: boolean }) {
  return <div className={`brand ${light ? 'brand-light' : ''}`} aria-label="AccessFlow">
    <span className="brand-symbol" aria-hidden="true"><i /><i /><i /></span>
    <span>access<span className="brand-thin">flow</span></span>
  </div>
}
