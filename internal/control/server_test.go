package control

import (
	"io"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"github.com/tony-ng-vn/codex-subscription-router/internal/mux"
	"github.com/tony-ng-vn/codex-subscription-router/internal/state"
)

func TestPreferAccountPersistsRoutingPreference(t *testing.T) {
	root := t.TempDir()
	store, err := state.Open(filepath.Join(root, "mux"), filepath.Join(root, "primary"))
	if err != nil {
		t.Fatal(err)
	}
	account, err := store.AddAccount("Work")
	if err != nil {
		t.Fatal(err)
	}
	multiplexer, err := mux.New(mux.Options{
		RealExecutable: "codex",
		Store:          store,
		Output:         io.Discard,
	})
	if err != nil {
		t.Fatal(err)
	}
	server := New("127.0.0.1:0", "test-token", multiplexer, false)
	request := httptest.NewRequest(
		http.MethodPost,
		"/v1/accounts/"+account.ID+"/prefer",
		strings.NewReader(`{}`),
	)
	request.Header.Set("X-Codex-Mux-Token", "test-token")
	response := httptest.NewRecorder()

	server.http.Handler.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("unexpected response: status=%d body=%s", response.Code, response.Body.String())
	}
	preferred, ok := store.PreferredAccount()
	if !ok || preferred.ID != account.ID {
		t.Fatalf("preference was not persisted: account=%#v ok=%v", preferred, ok)
	}
}
