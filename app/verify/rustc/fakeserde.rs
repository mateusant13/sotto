//! A stand-in for the `serde` crate, used ONLY by the rustc-only verification
//! path in this directory.
//!
//! It exists so `geometry.rs` and `memory.rs` can be compiled on a machine
//! where cargo is locked out by another build and the dependency tree cannot
//! be downloaded. It provides an empty `Serialize` derive: the geometry and
//! memory unit tests never serialise anything, so the derive's body is
//! irrelevant to what they assert.
//!
//! It is NOT part of the app. The app depends on the real serde.

extern crate proc_macro;

use proc_macro::TokenStream;

/// `#[serde(...)]` container attributes are declared here so that the real
/// sources carrying `#[serde(rename_all = "camelCase")]` still compile.
#[proc_macro_derive(Serialize, attributes(serde))]
pub fn derive_serialize(_input: TokenStream) -> TokenStream {
    TokenStream::new()
}