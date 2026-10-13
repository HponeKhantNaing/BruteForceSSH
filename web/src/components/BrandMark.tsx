type BrandMarkProps = {
  size?: number
  showWordmark?: boolean
  inverted?: boolean
}

export function BrandMark({ size = 34, showWordmark = true, inverted = false }: BrandMarkProps) {
  return (
    <div className={`logo-lockup ${inverted ? 'logo-lockup-inv' : ''}`}>
      <img
        className="brand-logo"
        src="/brutewatch-mark.png"
        alt=""
        width={size}
        height={size}
      />
      {showWordmark ? <strong>BruteWatch</strong> : null}
    </div>
  )
}
