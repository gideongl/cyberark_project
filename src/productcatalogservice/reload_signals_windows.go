//go:build windows

package main

import "os"

func reloadSignals() []os.Signal {
	return nil
}

func isReloadEnableSignal(os.Signal) bool {
	return false
}

func isReloadDisableSignal(os.Signal) bool {
	return false
}
