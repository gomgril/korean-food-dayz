class KF_PrepareWithHotWater: RecipeBase
{
    override void Init()
    {
        m_Name = KF_Lang.Text("STR_KF_R_SOAK_NOODLE");
        m_IsInstaRecipe = false;
        m_AnimationLength = 3 / CRAFTING_TIME_UNIT_SIZE;
        for (int i = 0; i < 2; i++)
        {
            m_MinDamageIngredient[i] = -1;
            m_MaxDamageIngredient[i] = 3;
            m_MinQuantityIngredient[i] = -1;
            m_MaxQuantityIngredient[i] = -1;
            m_IngredientSetHealth[i] = -1;
        }
        InsertIngredient(0, "KF_DryNoodles");
        InsertIngredient(1, "Pot");
        InsertIngredient(1, "Canteen");
        InsertIngredient(1, "WaterBottle");
    }
    override bool CanDo(ItemBase ingredients[], PlayerBase player)
    {
        return KF_Cooking.CanPrepare(KF_DryNoodles.Cast(ingredients[0]), ingredients[1], player);
    }
    override void Do(ItemBase ingredients[], PlayerBase player, array<ItemBase> results, float specialty_weight)
    {
        KF_Cooking.Prepare(KF_DryNoodles.Cast(ingredients[0]), ingredients[1], player);
    }
};
class KF_CraftChopsticks: RecipeBase
{
    override void Init()
    {
        m_Name = KF_Lang.Text("STR_KF_R_CHOPSTICKS");
        m_IsInstaRecipe = false;
        m_AnimationLength = 6 / CRAFTING_TIME_UNIT_SIZE;
        for (int i = 0; i < 2; i++)
        {
            m_MinDamageIngredient[i] = -1;
            m_MaxDamageIngredient[i] = 3;
            m_MinQuantityIngredient[i] = -1;
            m_MaxQuantityIngredient[i] = -1;
            m_IngredientSetHealth[i] = -1;
        }
        InsertIngredient(0, "WoodenStick");
        m_MinQuantityIngredient[0] = 1;
        InsertIngredient(1, "KitchenKnife");
        InsertIngredient(1, "SteakKnife");
        InsertIngredient(1, "StoneKnife");
        InsertIngredient(1, "BoneKnife");
        InsertIngredient(1, "HuntingKnife");
        InsertIngredient(1, "CombatKnife");
    }
    override bool CanDo(ItemBase ingredients[], PlayerBase player) { return true; }
    override void Do(ItemBase ingredients[], PlayerBase player, array<ItemBase> results, float specialty_weight)
    {
        if (!GetGame().IsServer()) return;
        EntityAI sticks = KF_Cooking.SpawnResult(player, "KF_Chopsticks");
        if (!sticks) return;
        sticks.SetHealth01("", "", ingredients[0].GetHealth01("", ""));
        ingredients[0].AddQuantity(-1);
        ingredients[1].AddHealth("", "", -1);
    }
};
modded class PluginRecipesManagerBase
{
    override void RegisterRecipies()
    {
        super.RegisterRecipies();
        RegisterRecipe(new KF_PrepareWithHotWater);
        RegisterRecipe(new KF_CraftChopsticks);
    }
};

