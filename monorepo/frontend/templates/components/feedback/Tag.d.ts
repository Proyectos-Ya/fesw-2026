import * as React from 'react';

/** Filter chip / removable tag. */
export interface TagProps {
  children?: React.ReactNode;
  /** Selected (teal) state. */
  active?: boolean;
  /** When provided, renders an × remove button. */
  onRemove?: (e: React.MouseEvent) => void;
  onClick?: (e: React.MouseEvent) => void;
  iconLeft?: React.ReactNode;
  style?: React.CSSProperties;
}

export function Tag(props: TagProps): JSX.Element;
