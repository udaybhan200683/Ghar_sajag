// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module S04 Product profile
// @requirements V01, AI01, AI07, E07, E10, NFR-08
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Product::ai is decided by GS_PRODUCT_AI and exposed through PRODUCT=base or ai in the Makefile. Invalid
// values fail the build. The runtime returns Disabled before calling a provider in the Base profile; the
// shared core remains identical. The older per-feature flags need separate enforcement review.

#pragma once
#ifndef GS_PRODUCT_AI
#define GS_PRODUCT_AI 0
#endif
#if GS_PRODUCT_AI != 0 && GS_PRODUCT_AI != 1
#error GS_PRODUCT_AI must be 0 or 1
#endif
namespace gs {
struct Product {
    static constexpr bool ai = GS_PRODUCT_AI == 1;
    static constexpr const char* version = "1.5.0";
    static constexpr const char* name = ai ? "Sarthi-AI" : "Parivar Saathi";
};
}
