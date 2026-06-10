import * as React from 'react';

/**
 * Primary call-to-action button for ProyectosYa.
 *
 * @startingPoint section="Forms" subtitle="Brand button — primary, accent, secondary, ghost, soft" viewport="700x150"
 */
export interface ButtonProps {
  children?: React.ReactNode;
  /** Visual style. Default "primary". */
  variant?: 'primary' | 'accent' | 'secondary' | 'ghost' | 'soft';
  /** Size. Default "md". */
  size?: 'sm' | 'md' | 'lg';
  /** Optional leading icon node (e.g. a Lucide <i data-lucide>). */
  iconLeft?: React.ReactNode;
  /** Optional trailing icon node. */
  iconRight?: React.ReactNode;
  fullWidth?: boolean;
  disabled?: boolean;
  type?: 'button' | 'submit' | 'reset';
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  style?: React.CSSProperties;
}

export function Button(props: ButtonProps): JSX.Element;
