import binascii

import romprofile
from romprofile import RomProfile
from codebytes import Code

b2h = binascii.hexlify
h2b = binascii.unhexlify


class ROM:
    def __init__(self, filestream, *, profile: RomProfile = None):
        data = filestream.read()
        self.banks = []
        for n in range(0x40):
            self.banks.append(bytearray(data[n * 0x4000:(n + 1) * 0x4000]))
        detected = romprofile.detect_profile(data)
        if profile is not None and profile.name != detected.name:
            raise ValueError(
                "ROM/profile mismatch: %s profile requested but the ROM looks like %s"
                % (profile.name, detected.name)
            )
        self.profile = profile if profile is not None else detected
        # Patch sites that could not be mapped to this ROM's profile.
        self.unmapped_patches = set()

    def patch(self, bank_nr, addr, old, new, *, fill_nop=False):
        # When `old` is an integer it is an end address; capture the length
        # before translating the address for a non-identity profile.
        old_len = (old - addr) if isinstance(old, int) else None

        check_old = True
        if not self.profile.is_identity:
            translated = self.profile.translate_patch(bank_nr, addr)
            if translated is None:
                if self.profile.strict:
                    raise romprofile.UnmappedPatchError(
                        "No %s mapping for patch at bank %02x addr %04x" % (self.profile.name, bank_nr, addr)
                    )
                self.unmapped_patches.add((bank_nr, addr))
                translated = addr
            bank_nr, addr = bank_nr, translated
            check_old = self.profile.verify_patches

        if isinstance(new, Code) and not self.profile.is_identity:
            new = b2h(self.profile.translate_code_bytes(bank_nr, h2b(new)))
        new = h2b(new)
        bank = self.banks[bank_nr]
        if old is not None:
            if old_len is not None:
                old = bank[addr:addr + old_len]
            else:
                old = h2b(old)
            if fill_nop:
                assert len(old) >= len(new), "Length mismatch: %d != %d (%s != %s)" % (len(old), len(new), b2h(old), b2h(new))
                new += b'\x00' * (len(old) - len(new))
            else:
                assert len(old) == len(new), "Length mismatch: %d != %d (%s != %s)" % (len(old), len(new), b2h(old), b2h(new))
            assert addr >= 0 and addr + len(old) <= 16 * 1024, f"{addr + len(old):04x}"
            if check_old and bank[addr:addr + len(old)] != old:
                if bank[addr:addr + len(old)] == new:
                    # Patch is already applied.
                    return
                loc = bank.find(old)
                while loc > -1:
                    print("Possible at:", hex(loc))
                    loc = bank.find(old, loc + 1)
                assert False, "Patch mismatch:\n%s !=\n%s at 0x%04x" % (b2h(bank[addr:addr + len(old)]), b2h(old), addr)
        bank[addr:addr + len(new)] = new
        assert len(bank) == 0x4000

    def fixHeader(self, *, name=None):
        # Preserve the region code (0x13F..0x142): it is used to detect the ROM
        # profile, and the title is overwritten below.
        region = bytes(self.banks[0][0x13F:0x143])
        if name is not None:
            name = name.encode("utf-8")
            name = (name + (b"\x00" * 15))[:15]
            self.banks[0][0x134:0x143] = name
        if region != b"\x00\x00\x00\x00":
            self.banks[0][0x13F:0x143] = region

        checksum = 0
        for c in self.banks[0][0x134:0x14D]:
            checksum -= c + 1
        self.banks[0][0x14D] = checksum & 0xFF

        # zero out the checksum before calculating it.
        self.banks[0][0x14E] = 0
        self.banks[0][0x14F] = 0
        checksum = 0
        for bank in self.banks:
            checksum = (checksum + sum(bank)) & 0xFFFF
        self.banks[0][0x14E] = checksum >> 8
        self.banks[0][0x14F] = checksum & 0xFF

    def save(self, file, *, name=None):
        if not self.profile.is_identity:
            print("Profile %s: %d code operand(s) translated, %d unmapped." % (
                self.profile.name,
                self.profile.code_operands_translated,
                self.profile.code_operands_unmapped,
            ))
        if self.unmapped_patches:
            print("Warning: %d patch site(s) had no %s mapping and used the English address:" % (
                len(self.unmapped_patches), self.profile.name))
            for bank_nr, addr in sorted(self.unmapped_patches)[:20]:
                print("  bank %02x addr %04x" % (bank_nr, addr))
        self.fixHeader(name=name)
        if isinstance(file, str):
            f = open(file, "wb")
            for bank in self.banks:
                f.write(bank)
            f.close()
            print("Saved:", file)
        else:
            for bank in self.banks:
                file.write(bank)

    def readHexSeed(self):
        return self.banks[0x3E][0x2F00:0x2F10].hex().upper()

    def readShortSettings(self):
        length = self.banks[0x3E][0x2F20]
        return self.banks[0x3E][0x2F21:0x2F21+length].decode('utf-8')
