//go:build !windows

package main

import (
	"os"
	"syscall"
)

func reloadSignals() []os.Signal {
	return []os.Signal{syscall.SIGUSR1, syscall.SIGUSR2}
}

func isReloadEnableSignal(sig os.Signal) bool {
	return sig == syscall.SIGUSR1
}

func isReloadDisableSignal(sig os.Signal) bool {
	return sig == syscall.SIGUSR2
}
