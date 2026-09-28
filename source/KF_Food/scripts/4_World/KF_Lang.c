// 표시 문장은 stringtable.csv의 STR_KF_* 키를 쓴다.
// 기본은 영어 키. 한글 패치(DayzTranslate_KR, CfgPatches LakeProject_Localization)가 있으면 STR_KF_*_KO 키를 쓴다.
class KF_Lang
{
    protected static int s_KF_Korean = -1;

    static bool IsKorean()
    {
        if (s_KF_Korean < 0)
        {
            s_KF_Korean = 0;
            if (GetGame() && GetGame().ConfigIsExisting("CfgPatches LakeProject_Localization")) s_KF_Korean = 1;
        }
        return s_KF_Korean == 1;
    }

    static bool IsKey(string key)
    {
        return key.IndexOf("$STR_KF_") == 0 || key.IndexOf("STR_KF_") == 0;
    }

    // "STR_KF_x" 또는 config 원문 "$STR_KF_x" -> 현재 언어의 문장
    static string Text(string key)
    {
        if (key.IndexOf("$") == 0) key = key.Substring(1, key.Length() - 1);
        if (key.IndexOf("STR_KF_") != 0) return key;
        if (IsKorean()) key = key + "_KO";
        return Widget.TranslateString("#" + key);
    }

    static string ConfigText(EntityAI entity, string entry)
    {
        return Text(entity.ConfigGetStringRaw(entry));
    }
};

modded class ItemBase
{
    override bool NameOverride(out string output)
    {
        string raw = ConfigGetStringRaw("displayName");
        if (KF_Lang.IsKey(raw))
        {
            output = KF_Lang.Text(raw);
            return true;
        }
        return super.NameOverride(output);
    }

    override bool DescriptionOverride(out string output)
    {
        string raw = ConfigGetStringRaw("descriptionShort");
        if (KF_Lang.IsKey(raw))
        {
            output = KF_Lang.Text(raw);
            return true;
        }
        return super.DescriptionOverride(output);
    }
};
