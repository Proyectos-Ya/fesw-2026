import React from 'react';
import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import { Button } from '../Button';

test('renders primary button by default', () => {
  render(<Button>Click me</Button>);
  const button = screen.getByRole('button', { name: /click me/i });
  expect(button).toBeInTheDocument();
  expect(button).toHaveClass('bg-blue-600');
});

test('renders secondary button variant', () => {
  render(<Button variant="secondary">Cancel</Button>);
  const button = screen.getByRole('button', { name: /cancel/i });
  expect(button).toBeInTheDocument();
  expect(button).toHaveClass('bg-gray-200');
});
