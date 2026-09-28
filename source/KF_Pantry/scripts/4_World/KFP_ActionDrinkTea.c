// The authored cup clips affect the upper body in standing/crouched stances.
// Prone needs its own authored cup support before it can be offered safely.
class KFP_ActionDrinkTea: ActionDrink
{
    void KFP_ActionDrinkTea()
    {
        m_StanceMask = DayZPlayerConstants.STANCEMASK_ERECT | DayZPlayerConstants.STANCEMASK_CROUCH;
    }

    override bool HasProneException()
    {
        return false;
    }
};

modded class ActionConstructor
{
    override void RegisterActions(TTypenameArray actions)
    {
        super.RegisterActions(actions);
        actions.Insert(KFP_ActionDrinkTea);
    }
};
