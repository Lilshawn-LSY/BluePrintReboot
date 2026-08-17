export interface ExclusiveMutationGate {
  tryAcquire(): number | null;
  release(token: number): boolean;
  isActive(): boolean;
}

export function createExclusiveMutationGate(): ExclusiveMutationGate;
