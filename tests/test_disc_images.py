"""The disc images: the DFS disc, and its ADFS copy (build.make_adfs_disc)
with every file, its addresses and the boot option the same."""

from stratagem.build import ADFS_DISC_FILEPATH, ADFS_TITLE


def files(root):
    return {source.path.rsplit(".", 1)[1]: (source.stat().load_address, source.stat().exec_address,
                                           source.read_bytes())
            for source in root.iterdir()}


def test_the_adfs_disc_holds_the_dfs_discs_files(game_build):
    from oaknut.adfs import ADFS
    from oaknut.dfs.dfs import DFS

    with DFS.from_file(game_build.disc_filepath, read_only=True) as dfs, \
            ADFS.from_file(ADFS_DISC_FILEPATH, read_only=True) as adfs:
        dfs_files = files(dfs.root / "$")
        assert "STRAT" in dfs_files and "PGAME" in dfs_files
        assert files(adfs.root) == dfs_files
        assert adfs.boot_option == dfs.boot_option
        assert adfs.title == ADFS_TITLE
