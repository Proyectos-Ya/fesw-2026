import * as React from 'react';

/** Single-line text field with label, hint and error states. */
export interface InputProps {
  label?: string;
  hint?: string;
  /** When set, the field renders in error state and shows this message. */
  error?: string;
  iconLeft?: React.ReactNode;
  value?: string;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  type?: string;
  disabled?: boolean;
  id?: string;
  style?: React.CSSProperties;
}

export function Input(props: InputProps): JSX.Element;
