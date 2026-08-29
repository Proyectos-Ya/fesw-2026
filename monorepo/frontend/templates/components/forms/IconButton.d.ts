import * as React from 'react';

/** Square icon-only button. Always pass `label` for accessibility. */
export interface IconButtonProps {
  icon: React.ReactNode;
  /** Accessible label (aria-label). */
  label: string;
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  style?: React.CSSProperties;
}

export function IconButton(props: IconButtonProps): JSX.Element;
