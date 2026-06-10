import * as React from 'react';

/** Surface container: white card, soft shadow, rounded-lg. */
export interface CardProps {
  children?: React.ReactNode;
  /** Inner padding in px. Default 20. */
  padding?: number;
  /** Lift + deepen shadow on hover (use for clickable cards). */
  interactive?: boolean;
  elevation?: 'none' | 'xs' | 'sm' | 'md' | 'lg';
  onClick?: (e: React.MouseEvent) => void;
  style?: React.CSSProperties;
}

export function Card(props: CardProps): JSX.Element;
