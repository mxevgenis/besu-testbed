const { ethers } = require("ethers");

const RPC = "https://snf-83472.ok-kno.grnetcloud.net/rpc"; // or http://83.212.80.192:30545
const FROM_PK = process.env.FROM_PK;

const RECIPIENTS = [
  "0x0E66db7d115B8F392eB7DFb8BaCb23675dAEB59E",
  "0x5E3a74f09D490F854e12A293E1d6abCBbEad6B60",
];

async function main() {
  if (FROM_PK == null || FROM_PK === "") throw new Error("Set FROM_PK env var");

  const provider = new ethers.providers.JsonRpcProvider(RPC);
  const wallet = new ethers.Wallet(FROM_PK, provider);

  const gasPrice = await provider.getGasPrice();

  for (const to of RECIPIENTS) {
    const tx = await wallet.sendTransaction({
      to,
      value: ethers.utils.parseEther("20"),
      gasLimit: 21000,
      gasPrice,
    });
    console.log("sent to " + to + ", tx: " + tx.hash);
    await tx.wait();
  }
}

main().catch(console.error);
