import * as React from 'react';

/** Small status pill. */
export interface BadgeProps {
  children?: React.ReactNode;
  tone?: 'neutral' | 'teal' | 'coral' | 'success' | 'warning' | 'danger' | 'info' | 'solid';
  /** Leading status dot. */
  dot?: boolean;
  iconLeft?: React.ReactNode;
  style?: React.CSSProperties;
}

export function Badge(props: BadgeProps): JSX.Element;
