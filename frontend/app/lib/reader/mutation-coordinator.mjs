export function createExclusiveMutationGate() {
  let activeToken = null;
  let nextToken = 0;
  return {
    tryAcquire() {
      if (activeToken !== null) return null;
      nextToken += 1;
      activeToken = nextToken;
      return activeToken;
    },
    release(token) {
      if (token !== activeToken) return false;
      activeToken = null;
      return true;
    },
    isActive() {
      return activeToken !== null;
    },
  };
}
