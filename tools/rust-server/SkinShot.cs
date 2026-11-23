// SkinShot — local test-server helper for shooting Workshop skins in game.
// Workshop skins that Facepunch has not accepted yet still render on a modded
// server when the item/entity carries their Workshop ID as skin.
//
// Chat commands (admins only):
//   /sauna [n]                   give every published Sauna item with its skin (n of each deployable)
//   /build                       building kit: plan, hammer, cupboard, lots of wood/stone/metal
//   /give <shortname> [skin] [n] give an item with a skin (e.g. /give locker 3840340102)
//   /skin <id>                   reskin the held item, or the entity you look at
//   /skin <id> look              reskin only the entity you look at
//   /t <hour>                    set time of day (e.g. /t 12, /t 22)
//   /bp                          unlock all blueprints (admins also get them on join)
// The same in the F1 console, without the slash: sauna [n], build, skin <id>, bp, giveskin <shortname> [skin] [n]
using System.Collections.Generic;
using UnityEngine;

namespace Oxide.Plugins
{
    [Info("SkinShot", "rustskin", "1.0.0")]
    [Description("Give and apply Workshop skins by ID on a local test server")]
    public class SkinShot : RustPlugin
    {
        static readonly List<KeyValuePair<string, ulong>> Sauna = new List<KeyValuePair<string, ulong>>
        {
            new KeyValuePair<string, ulong>("electric.furnace", 3840311723UL), // Sauna Stove
            new KeyValuePair<string, ulong>("bed",              3840333377UL), // Sauna Bench
            new KeyValuePair<string, ulong>("chair",            3840335380UL), // Sauna Chair
            new KeyValuePair<string, ulong>("box.wooden",       3840337593UL), // Sauna Stone Box
            new KeyValuePair<string, ulong>("locker",           3840340102UL), // Sauna Changing Locker
            new KeyValuePair<string, ulong>("burlap.headwrap",  3840341829UL), // Sauna Towel Wrap
            new KeyValuePair<string, ulong>("jacket.snow",      3840344106UL), // Sauna Robe
            new KeyValuePair<string, ulong>("door.hinged.wood", 3841006157UL), // Sauna Door
            new KeyValuePair<string, ulong>("furnace",          3841360723UL), // Sauna Boiler
            new KeyValuePair<string, ulong>("bucket.helmet",    3842910954UL), // Sauna Bucket
            new KeyValuePair<string, ulong>("tactical.gloves",  3843000799UL), // Sauna Mitts
        };

        // Wearables: one is enough even when /sauna <n> asks for more
        static readonly HashSet<string> Wear = new HashSet<string>
            { "burlap.headwrap", "jacket.snow", "bucket.helmet", "tactical.gloves" };

        // Building kit for /build
        static readonly string[][] Kit =
        {
            new[] { "building.planner", "1" }, new[] { "hammer", "1" }, new[] { "cupboard.tool", "1" },
            new[] { "wood", "100000" }, new[] { "stones", "100000" },
            new[] { "metal.fragments", "50000" }, new[] { "metal.refined", "2000" },
            new[] { "lowgradefuel", "500" },
        };

        void OnServerInitialized()
        {
            foreach (var kv in Sauna)
                if (ItemManager.FindItemDefinition(kv.Key) == null) PrintWarning($"Unknown shortname in Sauna list: {kv.Key}");
            Puts($"Sauna list: {Sauna.Count} items");
        }

        bool Allowed(BasePlayer p)
        {
            if (p.IsAdmin) return true;
            SendReply(p, "SkinShot: admins only");
            return false;
        }

        void Give(BasePlayer p, string shortname, ulong skin, int amount)
        {
            var item = ItemManager.CreateByName(shortname, amount, skin);
            if (item == null) { SendReply(p, $"Unknown item: {shortname}"); return; }
            p.GiveItem(item);
            SendReply(p, $"Given {item.info.displayName.english} x{amount}, skin {skin}");
        }

        // F1-console versions of the chat commands
        static string[] A(ConsoleSystem.Arg a)
        {
            int n = a.Args == null ? 0 : a.Args.Length;
            var r = new string[n];
            for (int i = 0; i < n; i++) r[i] = a.GetString(i);
            return r;
        }
        [ConsoleCommand("sauna")]    void CcSauna(ConsoleSystem.Arg a) { var p = a.Player(); if (p != null) CmdSauna(p, "sauna", A(a)); }
        [ConsoleCommand("skin")]     void CcSkin(ConsoleSystem.Arg a)  { var p = a.Player(); if (p != null) CmdSkin(p, "skin", A(a)); }
        [ConsoleCommand("build")]    void CcBuild(ConsoleSystem.Arg a) { var p = a.Player(); if (p != null) CmdBuild(p, "build", A(a)); }
        [ConsoleCommand("bp")]      void CcBp(ConsoleSystem.Arg a)    { var p = a.Player(); if (p != null) CmdBp(p, "bp", A(a)); }
        [ConsoleCommand("giveskin")] void CcGive(ConsoleSystem.Arg a)  { var p = a.Player(); if (p != null) CmdGive(p, "give", A(a)); }

        // Admins get every blueprint on join (and with /bp)
        void OnPlayerConnected(BasePlayer p)
        {
            if (p.IsAdmin) p.blueprints.UnlockAll();
        }

        [ChatCommand("bp")]
        void CmdBp(BasePlayer p, string cmd, string[] args)
        {
            if (!Allowed(p)) return;
            p.blueprints.UnlockAll();
            SendReply(p, "All blueprints unlocked");
        }

        // Crafting menu only lists Steam-inventory skins, so crafted Sauna items get their skin here
        void OnItemCraftFinished(ItemCraftTask task, Item item, ItemCrafter crafter)
        {
            if (item == null || item.skin != 0) return;
            foreach (var kv in Sauna)
                if (kv.Key == item.info.shortname) { item.skin = kv.Value; item.MarkDirty(); return; }
        }

        [ChatCommand("sauna")]
        void CmdSauna(BasePlayer p, string cmd, string[] args)
        {
            if (!Allowed(p)) return;
            int n = 1;
            if (args.Length > 0) int.TryParse(args[0], out n);
            n = Mathf.Clamp(n, 1, 20);
            foreach (var kv in Sauna) Give(p, kv.Key, kv.Value, Wear.Contains(kv.Key) ? 1 : n);
        }

        [ChatCommand("build")]
        void CmdBuild(BasePlayer p, string cmd, string[] args)
        {
            if (!Allowed(p)) return;
            foreach (var k in Kit) Give(p, k[0], 0, int.Parse(k[1]));
        }

        [ChatCommand("give")]
        void CmdGive(BasePlayer p, string cmd, string[] args)
        {
            if (!Allowed(p)) return;
            if (args.Length < 1) { SendReply(p, "/give <shortname> [skin] [amount]"); return; }
            ulong skin = 0; int amount = 1;
            if (args.Length > 1) ulong.TryParse(args[1], out skin);
            if (args.Length > 2) int.TryParse(args[2], out amount);
            Give(p, args[0], skin, Mathf.Max(1, amount));
        }

        [ChatCommand("skin")]
        void CmdSkin(BasePlayer p, string cmd, string[] args)
        {
            if (!Allowed(p)) return;
            ulong skin;
            if (args.Length < 1 || !ulong.TryParse(args[0], out skin)) { SendReply(p, "/skin <workshopId> [look]"); return; }
            bool lookOnly = args.Length > 1 && args[1] == "look";

            var held = p.GetActiveItem();
            if (!lookOnly && held != null)
            {
                held.skin = skin;
                var ent = held.GetHeldEntity();
                if (ent != null) { ent.skinID = skin; ent.SendNetworkUpdateImmediate(); }
                held.MarkDirty();
                SendReply(p, $"Held {held.info.shortname} -> skin {skin}");
                return;
            }

            RaycastHit hit;
            if (!Physics.Raycast(p.eyes.HeadRay(), out hit, 15f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
            { SendReply(p, "Nothing in front of you"); return; }
            var target = hit.GetEntity();
            if (target == null) { SendReply(p, "Not an entity"); return; }
            target.skinID = skin;
            target.SendNetworkUpdateImmediate();
            SendReply(p, $"{target.ShortPrefabName} -> skin {skin} (if it doesn't change, pick up and place again)");
        }

        [ChatCommand("t")]
        void CmdTime(BasePlayer p, string cmd, string[] args)
        {
            if (!Allowed(p)) return;
            float h;
            if (args.Length < 1 || !float.TryParse(args[0], out h)) { SendReply(p, "/t <hour 0-24>"); return; }
            TOD_Sky.Instance.Cycle.Hour = h;
            SendReply(p, $"Time {h}:00");
        }
    }
}
