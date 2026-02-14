import type { HTMLAttributes, ReactNode } from 'react'
import styles from './Card.module.css'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

export function Card({ children, padding = 'md', className = '', ...props }: CardProps) {
  return (
    <div className={`${styles.card} ${styles[`padding-${padding}`]} ${className}`} {...props}>
      {children}
    </div>
  )
}

interface CardHeaderProps {
  title: string
  subtitle?: string
  action?: ReactNode
}

export function CardHeader({ title, subtitle, action }: CardHeaderProps) {
  return (
    <div className={styles.header}>
      <div>
        <h3 className={styles.title}>{title}</h3>
        {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
      </div>
      {action && <div className={styles.action}>{action}</div>}
    </div>
  )
}
