// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title ShowPot — one-episode USDC prize escrow for Freak Town.
/// @notice The contract holds money, never opinions. It does NOT decide
/// who is funny: the closer (Freak Town backend multisig in production)
/// submits one authenticated result — Ella winner + Stream champion —
/// and the contract enforces money movement from there.
/// @dev Invariants (see Foundry invariant tests before any deploy):
///   1. sum(contributions) == totalPot, always.
///   2. ellaShare + streamShare + seasonShare == totalPot at finalize.
///   3. No claim before Locked. No double claim. No double refund.
///   4. Only the closer can finalize or enable refunds.
///   5. Refunds only in Refunded state, only to actual contributors.
/// Pull-based winner withdrawal. No upgradeability. USDC only.
contract ShowPot is ReentrancyGuard {
    using SafeERC20 for IERC20;

    /// @notice USDC token (immutable). Base mainnet: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA4b4.
    IERC20 public immutable USDC;
    /// @notice Closer role: submits the final result. Use a multisig in production.
    address public immutable CLOSER;
    /// @notice Season vault: receives the 10% season share at finalize.
    address public immutable SEASON_VAULT;
    /// @notice Contribution deadline (unix). Contributions after this revert.
    uint256 public immutable CLOSE_TIME;
    /// @notice Off-chain show id this pot belongs to (e.g. keccak256("ep_0042")).
    bytes32 public immutable SHOW_ID;

    // 70% Ella winner / 20% Stream champion / 10% season vault (basis points).
    uint256 private constant ELLA_BPS = 7000;
    uint256 private constant STREAM_BPS = 2000;
    uint256 private constant BPS_DENOM = 10_000;

    enum Status {
        Open, // accepting contributions
        Locked, // winner finalized, payouts claimable
        Claimed, // all winner shares withdrawn
        Refunded // emergency: contributors can pull back
    }

    Status public status;
    uint256 public totalPot;
    address public ellaWinner;
    address public streamChampion;
    mapping(address => uint256) public contributions;
    mapping(address => uint256) public pendingWithdrawals;
    mapping(address => bool) public refundClaimed;
    uint256 private outstandingShares;

    event Contribution(bytes32 indexed showId, address indexed wallet, uint256 amount, uint256 totalPot);
    event WinnersFinalized(
        bytes32 indexed showId,
        address indexed ellaWinner,
        address indexed streamChampion,
        uint256 ellaShare,
        uint256 streamShare,
        uint256 seasonShare
    );
    event PrizeClaimed(bytes32 indexed showId, address indexed winner, uint256 amount);
    event RefundsEnabled(bytes32 indexed showId);
    event RefundClaimed(bytes32 indexed showId, address indexed wallet, uint256 amount);

    error NotOpen();
    error PastDeadline();
    error NotCloser();
    error NothingToClaim();
    error AlreadyFinalized();
    error WrongState();

    constructor(IERC20 usdc, address closer, address seasonVault, uint256 closeTime, bytes32 showId) {
        require(address(usdc) != address(0), "usdc required");
        require(closer != address(0), "closer required");
        require(seasonVault != address(0), "season vault required");
        require(closeTime > block.timestamp, "closeTime must be in the future");
        USDC = usdc;
        CLOSER = closer;
        SEASON_VAULT = seasonVault;
        CLOSE_TIME = closeTime;
        SHOW_ID = showId;
    }

    /// @notice Contribute USDC to the pot. Caller must approve() first.
    function contribute(uint256 amount) external nonReentrant {
        if (status != Status.Open) revert NotOpen();
        if (block.timestamp > CLOSE_TIME) revert PastDeadline();
        require(amount > 0, "amount required");
        USDC.safeTransferFrom(msg.sender, address(this), amount);
        contributions[msg.sender] += amount;
        totalPot += amount;
        emit Contribution(SHOW_ID, msg.sender, amount, totalPot);
    }

    /// @notice Lock the result. Only the closer, only once, only while Open.
    /// @param ellaWinner_ Official champion (Ella selects). Required.
    /// @param streamChampion_ People's Champion, or address(0) if none —
    /// its 20% then rolls to the season vault with the base 10%.
    function finalizeWinners(address ellaWinner_, address streamChampion_) external nonReentrant {
        if (msg.sender != CLOSER) revert NotCloser();
        if (status != Status.Open) revert AlreadyFinalized();
        require(ellaWinner_ != address(0), "ella winner required");

        uint256 ellaShare = (totalPot * ELLA_BPS) / BPS_DENOM;
        uint256 streamShare = streamChampion_ == address(0) ? 0 : (totalPot * STREAM_BPS) / BPS_DENOM;
        // Dust from flooring lands in the season share. Deterministic.
        uint256 seasonShare = totalPot - ellaShare - streamShare;

        ellaWinner = ellaWinner_;
        streamChampion = streamChampion_;

        if (streamChampion_ == address(0) || streamChampion_ == ellaWinner_) {
            // Same wallet won both, or no stream champion: Ella side takes 90%.
            pendingWithdrawals[ellaWinner_] = ellaShare + streamShare;
            outstandingShares = ellaShare + streamShare;
        } else {
            pendingWithdrawals[ellaWinner_] = ellaShare;
            pendingWithdrawals[streamChampion_] = streamShare;
            outstandingShares = ellaShare + streamShare;
        }

        status = Status.Locked;

        if (seasonShare > 0) {
            USDC.safeTransfer(SEASON_VAULT, seasonShare);
        }

        emit WinnersFinalized(SHOW_ID, ellaWinner_, streamChampion_, ellaShare, streamShare, seasonShare);
    }

    /// @notice Winner pulls their share. Pull-based: nobody can push it wrong.
    function claimPrize() external nonReentrant {
        if (status != Status.Locked && status != Status.Claimed) revert WrongState();
        uint256 amount = pendingWithdrawals[msg.sender];
        if (amount == 0) revert NothingToClaim();
        pendingWithdrawals[msg.sender] = 0;
        outstandingShares -= amount;
        if (outstandingShares == 0) {
            status = Status.Claimed;
        }
        USDC.safeTransfer(msg.sender, amount);
        emit PrizeClaimed(SHOW_ID, msg.sender, amount);
    }

    /// @notice Emergency: open refunds. Only while Open (pre-finalize).
    /// Once winners are finalized, payouts are final — finality is the
    /// point of the escrow. A wrong finalize is a closer-key compromise,
    /// handled off-chain by the multisig, not by this contract.
    function enableRefunds() external {
        if (msg.sender != CLOSER) revert NotCloser();
        if (status != Status.Open) revert WrongState();
        status = Status.Refunded;
        emit RefundsEnabled(SHOW_ID);
    }

    /// @notice Contributor pulls their contribution back. Only in Refunded
    /// state, only actual contributors, only once.
    function claimRefund() external nonReentrant {
        if (status != Status.Refunded) revert WrongState();
        if (refundClaimed[msg.sender]) revert NothingToClaim();
        uint256 amount = contributions[msg.sender];
        if (amount == 0) revert NothingToClaim();
        refundClaimed[msg.sender] = true;
        contributions[msg.sender] = 0;
        USDC.safeTransfer(msg.sender, amount);
        emit RefundClaimed(SHOW_ID, msg.sender, amount);
    }
}
