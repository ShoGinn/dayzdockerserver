import { Loader2 } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import styles from './Button.module.css'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  isLoading?: boolean
  icon?: ReactNode
  children: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  icon,
  children,
  disabled,
  className = '',
  ...props
}: ButtonProps) {
  return (
    <button
      className={`${styles.button} ${styles[variant]} ${styles[size]} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <Loader2 className={styles.spinner} size={size === 'sm' ? 14 : 18} />
      ) : icon ? (
        <span className={styles.icon}>{icon}</span>
      ) : null}
      <span>{children}</span>
    </button>
  )
}
