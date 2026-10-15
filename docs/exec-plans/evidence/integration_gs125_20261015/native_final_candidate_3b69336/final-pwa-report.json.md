{
  "software_status": "FAIL",
  "physical_status": "NOT_RUN",
  "physically_qualified": false,
  "release_approved": false,
  "suite": "pwa",
  "source_head": "3b69336d1a661bf91a0d57dda56695764a16003d",
  "source_fingerprint": "a468c9311fa3c9942c0485b52138574c1641026fc797400cc27ca6850bf949c9",
  "source_unchanged": true,
  "build_profile": {
    "CXX": "",
    "HOST_CXX": "",
    "HOST_TOOLCHAIN_GUARD": "",
    "CXXFLAGS": "",
    "TRACE_FLAGS": "",
    "INCLUDES": "",
    "PRODUCT": "",
    "GS_IDF_EXPORT": "",
    "host_compiler": "d3c02c2eb999e2ce",
    "portable_crypto_sources": "ad5008d86e3a337d12bed44ce4e8d983db842db83ef0f245d6db69fb8b74bbd0",
    "python": "3.14.4 (main, Aug 20 2026, 10:41:58) [GCC 15.2.0]"
  },
  "tracked_dirty": false,
  "seconds": 49.783,
  "stages": [
    {
      "exit_code": 0,
      "seconds": 0,
      "status": "PASS",
      "id": "host-build",
      "command": [
        "make",
        "validation-build"
      ],
      "count": 1,
      "count_kind": "builds",
      "log": "evidence/validation_framework/pwa-1792047364328622824/host-build.log",
      "log_sha256": "e129c246b25933ea4bd5e5775fbecbf434d54808772f76caa86d174c758e44e2",
      "artifacts": {},
      "reused_from": "evidence/validation_framework/pwa-1792046117596214866/report.json",
      "components": [
        "node",
        "hub",
        "contract",
        "backend",
        "pwa",
        "tooling"
      ]
    },
    {
      "exit_code": 0,
      "seconds": 0,
      "status": "PASS",
      "id": "backend-receipts",
      "command": [
        "make",
        "hub-backend-commit-host-test"
      ],
      "count": 1,
      "count_kind": "assertion_groups",
      "log": "evidence/validation_framework/pwa-1792047364328622824/backend-receipts.log",
      "log_sha256": "a43254a6c35c669b440f5d9c7865cbbe4f6265cb71429449ea0c644dbf206982",
      "artifacts": {
        "build/hub_backend_commit_validation": "1efbfdc23b3afecd3d113c2f974de4ed7ce2508217aff5f91ad65c90b02e63b7"
      },
      "reused_from": "evidence/validation_framework/pwa-1792046117596214866/report.json",
      "components": [
        "hub",
        "contract",
        "backend"
      ]
    },
    {
      "exit_code": 0,
      "seconds": 0,
      "status": "PASS",
      "id": "contracts",
      "command": [
        "make",
        "contracts"
      ],
      "count": 1,
      "count_kind": "assertion_groups",
      "log": "evidence/validation_framework/pwa-1792047364328622824/contracts.log",
      "log_sha256": "0845e6c2c777d4a9437438522c3c95acddfbe017d7c09bad4e4b677ab617e268",
      "artifacts": {},
      "reused_from": "evidence/validation_framework/pwa-1792046117596214866/report.json",
      "components": [
        "contract",
        "backend",
        "pwa"
      ]
    },
    {
      "exit_code": 0,
      "seconds": 0,
      "status": "PASS",
      "id": "lab-build",
      "command": [
        "make",
        "lab-build"
      ],
      "count": 1,
      "count_kind": "builds",
      "log": "evidence/validation_framework/pwa-1792047364328622824/lab-build.log",
      "log_sha256": "d9bda1a0890baaeba6a92995ae6bd6d24636fd6a8d74f420acb6219322e9a2e9",
      "artifacts": {
        "build/ghar_sajag_interactive": "d1762d5b7d0014b55bb0c31707c2e31b430894b4f3cb1e7aa1aa89b19012d444"
      },
      "reused_from": "evidence/validation_framework/pwa-1792046117596214866/report.json",
      "components": [
        "backend",
        "pwa"
      ]
    },
    {
      "exit_code": 0,
      "seconds": 0,
      "status": "PASS",
      "id": "python",
      "command": [
        "python3",
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests/python",
        "-p",
        "test_*.py",
        "-v"
      ],
      "count": 470,
      "count_kind": "tests",
      "log": "evidence/validation_framework/pwa-1792047364328622824/python.log",
      "log_sha256": "e89c876f33b73199324ffbc4fce4f371caa71cc26a0d0fb04a907d87d1daba96",
      "artifacts": {},
      "reused_from": "evidence/validation_framework/pwa-1792046117596214866/report.json",
      "components": [
        "backend",
        "pwa",
        "tooling"
      ]
    },
    {
      "exit_code": 0,
      "seconds": 0,
      "status": "PASS",
      "id": "javascript",
      "command": [
        "make",
        "app-test"
      ],
      "count": 23,
      "count_kind": "tests",
      "log": "evidence/validation_framework/pwa-1792047364328622824/javascript.log",
      "log_sha256": "af728b29809168e19c5ec57c57d22d588f7116012550115726f13a4a9f1a3e4a",
      "artifacts": {},
      "reused_from": "evidence/validation_framework/pwa-1792046117596214866/report.json",
      "components": [
        "pwa"
      ]
    },
    {
      "exit_code": 0,
      "seconds": 0,
      "status": "PASS",
      "id": "functional",
      "command": [
        "python3",
        "validation/run_functional_suite.py"
      ],
      "count": 92,
      "count_kind": "assertion_groups",
      "log": "evidence/validation_framework/pwa-1792047364328622824/functional.log",
      "log_sha256": "2a03038e995d2032a1c9850e8f40baa99e2a217820cbd8ac4547564a79739edf",
      "artifacts": {},
      "reused_from": "evidence/validation_framework/pwa-1792046117596214866/report.json",
      "components": [
        "backend",
        "pwa"
      ]
    },
    {
      "exit_code": 0,
      "seconds": 0,
      "status": "PASS",
      "id": "dummy-streams",
      "command": [
        "python3",
        "validation/run_dummy_sensor_streams.py"
      ],
      "count": 5,
      "count_kind": "assertion_groups",
      "log": "evidence/validation_framework/pwa-1792047364328622824/dummy-streams.log",
      "log_sha256": "0e0637d2e52bc6ccdfe2c8974c271031d7d9e4d02125f32cd0b86200f8d65cb4",
      "artifacts": {},
      "reused_from": "evidence/validation_framework/pwa-1792046117596214866/report.json",
      "components": [
        "backend",
        "pwa"
      ]
    },
    {
      "exit_code": 0,
      "seconds": 0,
      "status": "PASS",
      "id": "http",
      "command": [
        "python3",
        "tests/simulation_http_test.py"
      ],
      "count": 17,
      "count_kind": "assertion_groups",
      "log": "evidence/validation_framework/pwa-1792047364328622824/http.log",
      "log_sha256": "1fba80d3cafb472eab53b1b24d5b79b617ec5f896268476fdd1c3f78067f7094",
      "artifacts": {},
      "reused_from": "evidence/validation_framework/pwa-1792046117596214866/report.json",
      "components": [
        "backend",
        "pwa"
      ]
    },
    {
      "exit_code": 0,
      "seconds": 0,
      "status": "PASS",
      "id": "bridge",
      "command": [
        "python3",
        "tests/pwa_bridge_test.py"
      ],
      "count": 13,
      "count_kind": "assertion_groups",
      "log": "evidence/validation_framework/pwa-1792047364328622824/bridge.log",
      "log_sha256": "d499d72b6ffc547bb003bd4f74d1946c0e581d96d7255fd650c3c9d184d5d1f9",
      "artifacts": {},
      "reused_from": "evidence/validation_framework/pwa-1792046117596214866/report.json",
      "components": [
        "backend",
        "pwa"
      ]
    },
    {
      "exit_code": 0,
      "seconds": 0,
      "status": "PASS",
      "id": "api",
      "command": [
        "python3",
        "tests/pwa_68_api_test.py"
      ],
      "count": 2,
      "count_kind": "assertion_groups",
      "log": "evidence/validation_framework/pwa-1792047364328622824/api.log",
      "log_sha256": "931183b4cd77ed266ee3d0bcdf28126898cd200c624dac95b1c2d6d3eff342ca",
      "artifacts": {},
      "reused_from": "evidence/validation_framework/pwa-1792046117596214866/report.json",
      "components": [
        "backend",
        "pwa"
      ]
    },
    {
      "exit_code": 0,
      "seconds": 0,
      "status": "PASS",
      "id": "frontend",
      "command": [
        "python3",
        "tests/pwa_68_frontend_test.py"
      ],
      "count": 2,
      "count_kind": "assertion_groups",
      "log": "evidence/validation_framework/pwa-1792047364328622824/frontend.log",
      "log_sha256": "55335ac7e9d57f989f7c224f8714c9d269a607a9245e78f9dae42350ddbf442f",
      "artifacts": {},
      "reused_from": "evidence/validation_framework/pwa-1792046117596214866/report.json",
      "components": [
        "backend",
        "pwa"
      ]
    },
    {
      "exit_code": 0,
      "seconds": 0,
      "status": "PASS",
      "id": "browser",
      "command": [
        "make",
        "playwright-gate"
      ],
      "count": 86,
      "count_kind": "tests",
      "log": "evidence/validation_framework/pwa-1792047364328622824/browser.log",
      "log_sha256": "ce4231d863988f5af8954394d965dcad23b8512c4d40f12e52bf38e83ea3f9cd",
      "artifacts": {
        "build/ghar_sajag_interactive": "d1762d5b7d0014b55bb0c31707c2e31b430894b4f3cb1e7aa1aa89b19012d444"
      },
      "reused_from": "evidence/validation_framework/pwa-1792046117596214866/report.json",
      "components": [
        "pwa"
      ]
    },
    {
      "exit_code": 0,
      "seconds": 49.049,
      "status": "FAIL",
      "id": "p0-full-product-e2e",
      "command": [
        "make",
        "p0-product-e2e",
        "P0_SCENARIOS="
      ],
      "count": 26,
      "count_kind": "scenario_checks",
      "log": "evidence/validation_framework/pwa-1792047364328622824/p0-full-product-e2e.log",
      "log_sha256": "a63dfb10c8c291edf8f9b5abbe6e5777b1cf2fb5192f73780c1b84f12013b6e0",
      "artifacts": {
        "build/p2d_cloud_contract_validation": "192daa9aacd6523b43c05c2d3013af5b9758a1186e976a325b8cfd215188df4d",
        "build/p0_board_stack_e2e_validation": "14191b020b4b8337851fb523a52b1d7b08bcc60281b8778a44942cefa44d8681"
      },
      "reused_from": null,
      "components": [
        "node",
        "hub",
        "contract",
        "backend",
        "pwa"
      ]
    },
    {
      "exit_code": 0,
      "seconds": 0,
      "status": "PASS",
      "id": "diagnostic-foundation",
      "command": [
        "python3",
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests/engineering_dashboard",
        "-p",
        "test_*.py",
        "-v"
      ],
      "count": 98,
      "count_kind": "tests",
      "log": "evidence/validation_framework/pwa-1792047364328622824/diagnostic-foundation.log",
      "log_sha256": "d8b099651f7c0298b55937f57134e922cc2d7be405e1af487939bdca3570ee2c",
      "artifacts": {},
      "reused_from": "evidence/validation_framework/pwa-1792046117596214866/report.json",
      "components": [
        "backend",
        "pwa"
      ]
    }
  ]
}
