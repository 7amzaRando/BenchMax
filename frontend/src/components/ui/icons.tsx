import React from 'react'

type P = { size?: number; className?: string }

const s = (n?: number) => n ?? 16

export const Zap = ({ size, className }: P) => (
  <svg width={s(size)} height={s(size)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden><path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z" /></svg>
)
export const Play = ({ size, className }: P) => (
  <svg width={s(size)} height={s(size)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden><path d="M8 5.14v14l11-7-11-7z" /></svg>
)
export const Activity = ({ size, className }: P) => (
  <svg width={s(size)} height={s(size)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden><path d="M22 12h-4l-3 9L9 3l-3 9H2" /></svg>
)
export const BarChart3 = ({ size, className }: P) => (
  <svg width={s(size)} height={s(size)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden><path d="M3 3v18h18" /><path d="M7 16v-4" /><path d="M12 16V8" /><path d="M17 16v-7" /></svg>
)
export const Trophy = ({ size, className }: P) => (
  <svg width={s(size)} height={s(size)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" /><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" /><path d="M4 22h16" /><path d="M10 22V12" /><path d="M14 22V12" /><path d="M7 12h10" /></svg>
)
export const Moon = ({ size, className }: P) => (
  <svg width={s(size)} height={s(size)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" /></svg>
)
export const Sun = ({ size, className }: P) => (
  <svg width={s(size)} height={s(size)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.93 4.93l1.42 1.42M17.66 17.66l1.42 1.42M4.93 19.07l1.42-1.42M17.66 6.34l1.42-1.42" /></svg>
)
export const ChevronRight = ({ size, className }: P) => (
  <svg width={s(size)} height={s(size)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden><path d="M9 18l6-6-6-6" /></svg>
)
export const Search = ({ size, className }: P) => (
  <svg width={s(size)} height={s(size)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden><circle cx="11" cy="11" r="7" /><path d="M20 20L16.5 16.5" /></svg>
)
export const Command = ({ size, className }: P) => (
  <svg width={s(size)} height={s(size)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden><path d="M15 6v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3" /></svg>
)
